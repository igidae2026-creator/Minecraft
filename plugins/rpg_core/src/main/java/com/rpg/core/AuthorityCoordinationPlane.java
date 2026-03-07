package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Explicit session authority + transfer ticket state machine used by runtime services.
 * This class is standalone so it can run with local persistence and be swapped for redis backing.
 */
public final class AuthorityCoordinationPlane {
    public enum TicketState {
        PENDING,
        CONSUMED,
        FAILED,
        EXPIRED
    }

    public record SessionAuthority(UUID playerId, String serverId, String leaseId, long leaseExpiresAt, long updatedAt) {
        public boolean expired(long now) {
            return leaseExpiresAt > 0L && now >= leaseExpiresAt;
        }
    }

    public record TransferTicket(String ticketId, UUID playerId, String sourceServer, String targetServer, long issuedAt,
                                 long expiresAt, long expectedProfileVersion, long expectedGuildVersion,
                                 String sourceLeaseId, TicketState state, String failureReason) {
        public boolean expired(long now) {
            return expiresAt > 0L && now >= expiresAt;
        }
    }

    private final ConcurrentMap<UUID, SessionAuthority> liveAuthorities = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, TransferTicket> tickets = new ConcurrentHashMap<>();

    private final AtomicLong sessionOwnershipConflicts = new AtomicLong();
    private final AtomicLong splitBrainDetections = new AtomicLong();
    private final AtomicLong duplicateLoginRejects = new AtomicLong();
    private final AtomicLong transferFenceRejects = new AtomicLong();
    private final AtomicLong leaseExpiries = new AtomicLong();
    private final AtomicLong expiredTicketTransitions = new AtomicLong();

    public TransferTicket issueTicket(UUID playerId, String sourceServer, String targetServer,
                                      long expectedProfileVersion, long expectedGuildVersion,
                                      String sourceLeaseId, long now, long ttlMillis) {
        String ticketId = UUID.randomUUID().toString().replace("-", "");
        TransferTicket ticket = new TransferTicket(
            ticketId,
            playerId,
            normalize(sourceServer),
            normalize(targetServer),
            now,
            now + Math.max(1_000L, ttlMillis),
            expectedProfileVersion,
            expectedGuildVersion,
            sourceLeaseId == null ? "" : sourceLeaseId,
            TicketState.PENDING,
            ""
        );
        tickets.put(ticketId, ticket);
        return ticket;
    }

    public TransferTicket consumeTicket(String ticketId, UUID playerId, String targetServer, long now) {
        TransferTicket ticket = tickets.get(ticketId);
        if (ticket == null) {
            transferFenceRejects.incrementAndGet();
            return null;
        }
        if (ticket.state() != TicketState.PENDING) {
            transferFenceRejects.incrementAndGet();
            return failTicket(ticket, "already_" + ticket.state().name().toLowerCase(Locale.ROOT));
        }
        if (!ticket.playerId().equals(playerId)) {
            transferFenceRejects.incrementAndGet();
            return failTicket(ticket, "player_mismatch");
        }
        if (!ticket.targetServer().equalsIgnoreCase(normalize(targetServer))) {
            transferFenceRejects.incrementAndGet();
            return failTicket(ticket, "target_mismatch");
        }
        if (ticket.expired(now)) {
            leaseExpiries.incrementAndGet();
            transferFenceRejects.incrementAndGet();
            return failTicket(ticket, "expired");
        }
        TransferTicket consumed = new TransferTicket(
            ticket.ticketId(), ticket.playerId(), ticket.sourceServer(), ticket.targetServer(),
            ticket.issuedAt(), ticket.expiresAt(), ticket.expectedProfileVersion(), ticket.expectedGuildVersion(),
            ticket.sourceLeaseId(), TicketState.CONSUMED, "");
        tickets.put(consumed.ticketId(), consumed);
        return consumed;
    }

    public SessionAuthority claimSession(UUID playerId, String serverId, String leaseId, long now, long ttlMillis) {
        SessionAuthority next = new SessionAuthority(playerId, normalize(serverId), leaseId, now + Math.max(1_000L, ttlMillis), now);
        SessionAuthority existing = liveAuthorities.put(playerId, next);
        if (existing != null && !existing.expired(now) && !existing.serverId().equalsIgnoreCase(next.serverId())) {
            splitBrainDetections.incrementAndGet();
            sessionOwnershipConflicts.incrementAndGet();
        }
        return next;
    }

    public void sweepExpiredState(long now) {
        for (Map.Entry<UUID, SessionAuthority> entry : liveAuthorities.entrySet()) {
            SessionAuthority authority = entry.getValue();
            if (authority == null || !authority.expired(now)) {
                continue;
            }
            liveAuthorities.remove(entry.getKey(), authority);
        }
        for (Map.Entry<String, TransferTicket> entry : tickets.entrySet()) {
            TransferTicket ticket = entry.getValue();
            if (ticket == null) {
                continue;
            }
            if ((ticket.state() == TicketState.PENDING || ticket.state() == TicketState.FAILED) && ticket.expired(now)) {
                markExpired(ticket, "expired");
            }
        }
    }

    public boolean rejectDuplicateLogin(UUID playerId, String serverId, long now) {
        SessionAuthority existing = liveAuthorities.get(playerId);
        if (existing == null || existing.expired(now)) {
            return false;
        }
        boolean reject = existing.serverId().equalsIgnoreCase(normalize(serverId));
        if (reject) {
            duplicateLoginRejects.incrementAndGet();
        }
        return reject;
    }

    public void releaseSession(UUID playerId) {
        if (playerId != null) {
            liveAuthorities.remove(playerId);
        }
    }

    public YamlConfiguration metricsSnapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("session_ownership_conflicts", sessionOwnershipConflicts.get());
        yaml.set("split_brain_detections", splitBrainDetections.get());
        yaml.set("duplicate_login_rejects", duplicateLoginRejects.get());
        yaml.set("transfer_fence_rejects", transferFenceRejects.get());
        yaml.set("transfer_lease_expiry", leaseExpiries.get());
        yaml.set("ticket_expired_transitions", expiredTicketTransitions.get());
        yaml.set("transfer_tickets_total", tickets.size());
        long pending = 0L;
        long consumed = 0L;
        long failed = 0L;
        long expired = 0L;
        for (TransferTicket ticket : tickets.values()) {
            if (ticket == null) {
                continue;
            }
            if (ticket.state() == TicketState.PENDING) {
                pending++;
            } else if (ticket.state() == TicketState.CONSUMED) {
                consumed++;
            } else if (ticket.state() == TicketState.FAILED) {
                failed++;
            } else if (ticket.state() == TicketState.EXPIRED) {
                expired++;
            }
        }
        yaml.set("transfer_tickets_pending", pending);
        yaml.set("transfer_tickets_consumed", consumed);
        yaml.set("transfer_tickets_failed", failed);
        yaml.set("transfer_tickets_expired", expired);
        yaml.set("live_authority_sessions", liveAuthorities.size());
        return yaml;
    }

    private TransferTicket markExpired(TransferTicket ticket, String reason) {
        TransferTicket expired = new TransferTicket(
            ticket.ticketId(),
            ticket.playerId(),
            ticket.sourceServer(),
            ticket.targetServer(),
            ticket.issuedAt(),
            ticket.expiresAt(),
            ticket.expectedProfileVersion(),
            ticket.expectedGuildVersion(),
            ticket.sourceLeaseId(),
            TicketState.EXPIRED,
            reason
        );
        if (tickets.replace(expired.ticketId(), ticket, expired)) {
            leaseExpiries.incrementAndGet();
            expiredTicketTransitions.incrementAndGet();
            return expired;
        }
        return tickets.getOrDefault(ticket.ticketId(), expired);
    }

    private TransferTicket failTicket(TransferTicket ticket, String reason) {
        TransferTicket failed = new TransferTicket(
            ticket.ticketId(),
            ticket.playerId(),
            ticket.sourceServer(),
            ticket.targetServer(),
            ticket.issuedAt(),
            ticket.expiresAt(),
            ticket.expectedProfileVersion(),
            ticket.expectedGuildVersion(),
            ticket.sourceLeaseId(),
            TicketState.FAILED,
            reason
        );
        tickets.put(failed.ticketId(), failed);
        return failed;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
