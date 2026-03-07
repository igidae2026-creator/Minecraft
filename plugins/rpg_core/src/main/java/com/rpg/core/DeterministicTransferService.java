package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class DeterministicTransferService {
    public enum TransferState {
        INITIATED,
        PERSISTING,
        LEASED,
        ACTIVATING,
        ACTIVE,
        FAILED,
        EXPIRED
    }

    public record TransferRecord(
        String transferId,
        UUID playerId,
        String sourceServer,
        String targetServer,
        String leaseId,
        long durableVersionBarrier,
        long fenceToken,
        TransferState state,
        boolean mutationFreeze,
        boolean staleLoadRefused,
        boolean refunded,
        long createdAt,
        long updatedAt,
        List<String> transitionLog
    ) {}

    private final ConcurrentMap<String, TransferRecord> transfers = new ConcurrentHashMap<>();
    private final AtomicLong staleLoadRejections = new AtomicLong();
    private final AtomicLong rollbackRefunds = new AtomicLong();
    private final AtomicLong leaseVerificationFailures = new AtomicLong();

    public TransferRecord begin(UUID playerId, String sourceServer, String targetServer, String leaseId, long durableVersionBarrier, long fenceToken) {
        long now = Instant.now().toEpochMilli();
        String transferId = "transfer_" + UUID.randomUUID().toString().replace("-", "");
        List<String> log = new ArrayList<>();
        log.add(now + ":INITIATED");
        TransferRecord record = new TransferRecord(
            transferId,
            playerId,
            normalize(sourceServer),
            normalize(targetServer),
            normalize(leaseId),
            durableVersionBarrier,
            fenceToken,
            TransferState.INITIATED,
            false,
            false,
            false,
            now,
            now,
            log
        );
        transfers.put(transferId, record);
        return record;
    }

    public TransferRecord transition(String transferId, TransferState nextState, String note) {
        TransferRecord current = transfers.get(transferId);
        if (current == null) {
            return null;
        }
        long now = Instant.now().toEpochMilli();
        List<String> log = new ArrayList<>(current.transitionLog());
        log.add(now + ":" + nextState.name() + (note == null || note.isBlank() ? "" : ":" + note));
        TransferRecord next = new TransferRecord(
            current.transferId(),
            current.playerId(),
            current.sourceServer(),
            current.targetServer(),
            current.leaseId(),
            current.durableVersionBarrier(),
            current.fenceToken(),
            nextState,
            current.mutationFreeze(),
            current.staleLoadRefused(),
            current.refunded(),
            current.createdAt(),
            now,
            log
        );
        transfers.put(transferId, next);
        return next;
    }

    public TransferRecord freezeMutations(String transferId) {
        return update(transferId, "mutation_freeze");
    }

    public TransferRecord refuseStaleLoad(String transferId, long observedVersion) {
        staleLoadRejections.incrementAndGet();
        return update(transferId, "stale_load_refusal:" + observedVersion, true, null);
    }

    public TransferRecord verifyLease(String transferId, String expectedLeaseId) {
        TransferRecord current = transfers.get(transferId);
        if (current == null) {
            return null;
        }
        if (!current.leaseId().equals(normalize(expectedLeaseId))) {
            leaseVerificationFailures.incrementAndGet();
            return transition(transferId, TransferState.FAILED, "lease_verification_failed");
        }
        return current;
    }

    public TransferRecord refund(String transferId, String reason) {
        rollbackRefunds.incrementAndGet();
        return update(transferId, "refund:" + normalize(reason), null, true);
    }

    private TransferRecord update(String transferId, String note) {
        return update(transferId, note, null, null);
    }

    private TransferRecord update(String transferId, String note, Boolean staleLoadRefused, Boolean refunded) {
        TransferRecord current = transfers.get(transferId);
        if (current == null) {
            return null;
        }
        long now = Instant.now().toEpochMilli();
        List<String> log = new ArrayList<>(current.transitionLog());
        log.add(now + ":" + note);
        TransferRecord next = new TransferRecord(
            current.transferId(),
            current.playerId(),
            current.sourceServer(),
            current.targetServer(),
            current.leaseId(),
            current.durableVersionBarrier(),
            current.fenceToken(),
            current.state(),
            true,
            staleLoadRefused != null ? staleLoadRefused : current.staleLoadRefused(),
            refunded != null ? refunded : current.refunded(),
            current.createdAt(),
            now,
            log
        );
        transfers.put(transferId, next);
        return next;
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("transfers", transfers.size());
        yaml.set("states", Arrays.stream(TransferState.values()).map(Enum::name).toList());
        yaml.set("stale_load_rejections", staleLoadRejections.get());
        yaml.set("rollback_refunds", rollbackRefunds.get());
        yaml.set("lease_verification_failures", leaseVerificationFailures.get());
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
