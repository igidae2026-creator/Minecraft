package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Truthful in-repo coordination substrate used when external distributed locking
 * is unavailable or only mirrored. This preserves deterministic authority semantics
 * without claiming Redis guarantees that are not enforced by the runtime itself.
 */
public final class SessionAuthorityService {
    public enum OwnershipState {
        REGISTERED,
        LEASED,
        RECONNECT_HELD,
        TRANSFERRING,
        ACTIVE,
        INVALIDATED,
        EXPIRED
    }

    public record SessionOwnership(
        UUID playerId,
        String ownerServer,
        String ownerEpoch,
        String leaseId,
        long leaseExpiresAt,
        long lastHeartbeatAt,
        long reconnectUntil,
        OwnershipState state,
        String transferId,
        long fenceToken
    ) {
        public boolean expired(long now) {
            return leaseExpiresAt > 0L && now >= leaseExpiresAt;
        }
    }

    public record TransferActivation(
        String transferId,
        UUID playerId,
        String sourceServer,
        String targetServer,
        String sourceLeaseId,
        String targetLeaseId,
        long issuedAt,
        long expiresAt,
        long sourceFenceToken,
        long targetFenceToken,
        String expectedOwnerEpoch,
        String state,
        String failureReason
    ) {
        public boolean expired(long now) {
            return expiresAt > 0L && now >= expiresAt;
        }
    }

    private final Path coordinationRoot;
    private final ConcurrentMap<UUID, SessionOwnership> ownerships = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, TransferActivation> transfers = new ConcurrentHashMap<>();
    private final AtomicLong fenceCounter = new AtomicLong(1L);
    private final AtomicLong ownershipConflicts = new AtomicLong();
    private final AtomicLong duplicateLoginRejects = new AtomicLong();
    private final AtomicLong splitBrainDetections = new AtomicLong();
    private final AtomicLong reconnectReclaims = new AtomicLong();
    private final AtomicLong activationConfirmations = new AtomicLong();
    private final AtomicLong crashInvalidations = new AtomicLong();
    private final AtomicLong expiries = new AtomicLong();

    public SessionAuthorityService(Path coordinationRoot) {
        this.coordinationRoot = coordinationRoot;
    }

    public SessionOwnership claim(UUID playerId, String ownerServer, String ownerEpoch, String leaseId, long now, long ttlMillis) {
        SessionOwnership next = new SessionOwnership(
            playerId,
            normalize(ownerServer),
            normalize(ownerEpoch),
            normalize(leaseId),
            now + Math.max(1_000L, ttlMillis),
            now,
            0L,
            OwnershipState.LEASED,
            "",
            fenceCounter.getAndIncrement()
        );
        SessionOwnership existing = ownerships.put(playerId, next);
        if (existing != null && !existing.expired(now) && !existing.ownerServer().equals(next.ownerServer())) {
            ownershipConflicts.incrementAndGet();
            splitBrainDetections.incrementAndGet();
        }
        return next;
    }

    public boolean rejectDuplicateLogin(UUID playerId, String serverId, long now) {
        SessionOwnership existing = ownerships.get(playerId);
        if (existing == null || existing.expired(now)) {
            return false;
        }
        if (existing.ownerServer().equals(normalize(serverId)) && existing.state() != OwnershipState.TRANSFERRING) {
            duplicateLoginRejects.incrementAndGet();
            return true;
        }
        return false;
    }

    public SessionOwnership heartbeat(UUID playerId, String leaseId, long now, long ttlMillis) {
        SessionOwnership current = ownerships.get(playerId);
        if (current == null || !current.leaseId().equals(normalize(leaseId))) {
            return null;
        }
        SessionOwnership refreshed = new SessionOwnership(
            current.playerId(),
            current.ownerServer(),
            current.ownerEpoch(),
            current.leaseId(),
            now + Math.max(1_000L, ttlMillis),
            now,
            current.reconnectUntil(),
            current.state(),
            current.transferId(),
            current.fenceToken()
        );
        ownerships.put(playerId, refreshed);
        return refreshed;
    }

    public SessionOwnership holdReconnect(UUID playerId, long now, long reconnectMillis) {
        SessionOwnership current = ownerships.get(playerId);
        if (current == null) {
            return null;
        }
        SessionOwnership held = new SessionOwnership(
            current.playerId(),
            current.ownerServer(),
            current.ownerEpoch(),
            current.leaseId(),
            current.leaseExpiresAt(),
            now,
            now + Math.max(1_000L, reconnectMillis),
            OwnershipState.RECONNECT_HELD,
            current.transferId(),
            current.fenceToken()
        );
        ownerships.put(playerId, held);
        return held;
    }

    public SessionOwnership reclaim(UUID playerId, String ownerServer, String ownerEpoch, String leaseId, long now, long ttlMillis) {
        SessionOwnership reclaimed = claim(playerId, ownerServer, ownerEpoch, leaseId, now, ttlMillis);
        reconnectReclaims.incrementAndGet();
        return reclaimed;
    }

    public TransferActivation beginTransfer(UUID playerId, String sourceServer, String targetServer, String sourceLeaseId,
                                            String targetLeaseId, String expectedOwnerEpoch, long now, long ttlMillis) {
        SessionOwnership ownership = ownerships.get(playerId);
        long sourceFence = ownership == null ? fenceCounter.getAndIncrement() : ownership.fenceToken();
        long targetFence = fenceCounter.getAndIncrement();
        String transferId = "xfer_" + UUID.randomUUID().toString().replace("-", "");
        TransferActivation activation = new TransferActivation(
            transferId,
            playerId,
            normalize(sourceServer),
            normalize(targetServer),
            normalize(sourceLeaseId),
            normalize(targetLeaseId),
            now,
            now + Math.max(1_000L, ttlMillis),
            sourceFence,
            targetFence,
            normalize(expectedOwnerEpoch),
            "ACTIVATING",
            ""
        );
        transfers.put(transferId, activation);
        if (ownership != null) {
            ownerships.put(playerId, new SessionOwnership(
                ownership.playerId(),
                ownership.ownerServer(),
                ownership.ownerEpoch(),
                ownership.leaseId(),
                ownership.leaseExpiresAt(),
                now,
                ownership.reconnectUntil(),
                OwnershipState.TRANSFERRING,
                transferId,
                ownership.fenceToken()
            ));
        }
        return activation;
    }

    public TransferActivation confirmActivation(String transferId, String expectedOwnerEpoch, long now) {
        TransferActivation current = transfers.get(transferId);
        if (current == null) {
            return null;
        }
        if (!current.expectedOwnerEpoch().equals(normalize(expectedOwnerEpoch))) {
            splitBrainDetections.incrementAndGet();
            TransferActivation failed = new TransferActivation(
                current.transferId(), current.playerId(), current.sourceServer(), current.targetServer(),
                current.sourceLeaseId(), current.targetLeaseId(), current.issuedAt(), current.expiresAt(),
                current.sourceFenceToken(), current.targetFenceToken(), current.expectedOwnerEpoch(), "FAILED", "epoch_mismatch"
            );
            transfers.put(transferId, failed);
            return failed;
        }
        TransferActivation active = new TransferActivation(
            current.transferId(), current.playerId(), current.sourceServer(), current.targetServer(),
            current.sourceLeaseId(), current.targetLeaseId(), current.issuedAt(), current.expiresAt(),
            current.sourceFenceToken(), current.targetFenceToken(), current.expectedOwnerEpoch(), "ACTIVE", ""
        );
        transfers.put(transferId, active);
        activationConfirmations.incrementAndGet();
        SessionOwnership ownership = ownerships.get(current.playerId());
        if (ownership != null) {
            ownerships.put(current.playerId(), new SessionOwnership(
                ownership.playerId(),
                current.targetServer(),
                ownership.ownerEpoch(),
                current.targetLeaseId(),
                current.expiresAt(),
                now,
                0L,
                OwnershipState.ACTIVE,
                current.transferId(),
                current.targetFenceToken()
            ));
        }
        return active;
    }

    public void invalidateCrashedOwner(UUID playerId, String ownerServer, long now) {
        SessionOwnership current = ownerships.get(playerId);
        if (current == null || !current.ownerServer().equals(normalize(ownerServer))) {
            return;
        }
        ownerships.put(playerId, new SessionOwnership(
            current.playerId(),
            current.ownerServer(),
            current.ownerEpoch(),
            current.leaseId(),
            current.leaseExpiresAt(),
            now,
            current.reconnectUntil(),
            OwnershipState.INVALIDATED,
            current.transferId(),
            current.fenceToken()
        ));
        crashInvalidations.incrementAndGet();
    }

    public void release(UUID playerId) {
        if (playerId != null) {
            ownerships.remove(playerId);
        }
    }

    public void sweep(long now) {
        for (Map.Entry<UUID, SessionOwnership> entry : new ArrayList<>(ownerships.entrySet())) {
            SessionOwnership current = entry.getValue();
            if (current == null) {
                continue;
            }
            boolean reconnectExpired = current.reconnectUntil() > 0L && now >= current.reconnectUntil();
            if (current.expired(now) || reconnectExpired) {
                ownerships.put(entry.getKey(), new SessionOwnership(
                    current.playerId(),
                    current.ownerServer(),
                    current.ownerEpoch(),
                    current.leaseId(),
                    current.leaseExpiresAt(),
                    now,
                    current.reconnectUntil(),
                    OwnershipState.EXPIRED,
                    current.transferId(),
                    current.fenceToken()
                ));
                expiries.incrementAndGet();
            }
        }
        for (Map.Entry<String, TransferActivation> entry : new ArrayList<>(transfers.entrySet())) {
            TransferActivation current = entry.getValue();
            if (current != null && current.expired(now) && !"ACTIVE".equals(current.state()) && !"FAILED".equals(current.state())) {
                transfers.put(entry.getKey(), new TransferActivation(
                    current.transferId(), current.playerId(), current.sourceServer(), current.targetServer(),
                    current.sourceLeaseId(), current.targetLeaseId(), current.issuedAt(), current.expiresAt(),
                    current.sourceFenceToken(), current.targetFenceToken(), current.expectedOwnerEpoch(), "EXPIRED", "lease_expired"
                ));
                expiries.incrementAndGet();
            }
        }
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("coordination_root", coordinationRoot == null ? "" : coordinationRoot.toString());
        yaml.set("ownerships", ownerships.size());
        yaml.set("transfers", transfers.size());
        yaml.set("session_ownership_conflicts", ownershipConflicts.get());
        yaml.set("duplicate_login_rejects", duplicateLoginRejects.get());
        yaml.set("split_brain_detections", splitBrainDetections.get());
        yaml.set("reconnect_reclaims", reconnectReclaims.get());
        yaml.set("activation_confirmations", activationConfirmations.get());
        yaml.set("crash_owner_invalidations", crashInvalidations.get());
        yaml.set("expiries", expiries.get());
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
