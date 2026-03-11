package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class PartyService {
    public record Party(
        String partyId,
        UUID leaderId,
        Set<UUID> members,
        long createdAt,
        long updatedAt
    ) {}

    private final ConcurrentMap<String, Party> parties = new ConcurrentHashMap<>();
    private final ConcurrentMap<UUID, String> membership = new ConcurrentHashMap<>();
    private final ConcurrentMap<UUID, UUID> invites = new ConcurrentHashMap<>();
    private final AtomicLong transfers = new AtomicLong();

    public Party createOrGet(UUID leaderId) {
        String existing = membership.get(leaderId);
        if (existing != null && parties.containsKey(existing)) {
            return parties.get(existing);
        }
        String partyId = "party_" + UUID.randomUUID().toString().replace("-", "");
        Party party = new Party(partyId, leaderId, new LinkedHashSet<>(List.of(leaderId)), Instant.now().toEpochMilli(), Instant.now().toEpochMilli());
        parties.put(partyId, party);
        membership.put(leaderId, partyId);
        return party;
    }

    public void invite(UUID leaderId, UUID invitedId) {
        Party party = createOrGet(leaderId);
        if (!party.leaderId().equals(leaderId)) {
            return;
        }
        invites.put(invitedId, leaderId);
    }

    public Party accept(UUID invitedId) {
        UUID leaderId = invites.remove(invitedId);
        if (leaderId == null) {
            return null;
        }
        Party party = createOrGet(leaderId);
        Set<UUID> nextMembers = new LinkedHashSet<>(party.members());
        nextMembers.add(invitedId);
        Party next = new Party(party.partyId(), party.leaderId(), nextMembers, party.createdAt(), Instant.now().toEpochMilli());
        parties.put(next.partyId(), next);
        membership.put(invitedId, next.partyId());
        return next;
    }

    public Party leave(UUID memberId) {
        String partyId = membership.remove(memberId);
        if (partyId == null) {
            return null;
        }
        Party party = parties.get(partyId);
        if (party == null) {
            return null;
        }
        Set<UUID> nextMembers = new LinkedHashSet<>(party.members());
        nextMembers.remove(memberId);
        if (nextMembers.isEmpty()) {
            parties.remove(partyId);
            return null;
        }
        UUID nextLeader = party.leaderId().equals(memberId) ? nextMembers.iterator().next() : party.leaderId();
        Party next = new Party(party.partyId(), nextLeader, nextMembers, party.createdAt(), Instant.now().toEpochMilli());
        parties.put(partyId, next);
        return next;
    }

    public Party partyFor(UUID memberId) {
        String partyId = membership.get(memberId);
        return partyId == null ? null : parties.get(partyId);
    }

    public boolean isLeader(UUID memberId) {
        Party party = partyFor(memberId);
        return party != null && party.leaderId().equals(memberId);
    }

    public void markTransfer() {
        transfers.incrementAndGet();
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("parties", parties.size());
        yaml.set("memberships", membership.size());
        yaml.set("pending_invites", invites.size());
        yaml.set("party_transfers", transfers.get());
        Map<String, Object> active = new LinkedHashMap<>();
        for (Party party : parties.values()) {
            List<String> members = new ArrayList<>();
            for (UUID member : party.members()) {
                members.add(member.toString());
            }
            active.put(party.partyId(), Map.of(
                "leader", party.leaderId().toString(),
                "members", members,
                "updated_at", party.updatedAt()
            ));
        }
        yaml.set("active", active);
        return yaml;
    }
}
