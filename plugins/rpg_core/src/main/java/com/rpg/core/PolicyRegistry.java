package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class PolicyRegistry {
    public record PolicyRecord(
        String policyId,
        String versionId,
        String artifactId,
        String state,
        String activatedBy,
        long createdAt,
        long updatedAt,
        List<String> metrics
    ) {}

    private final ConcurrentMap<String, PolicyRecord> records = new ConcurrentHashMap<>();
    private final AtomicLong activations = new AtomicLong();
    private final AtomicLong rollbacks = new AtomicLong();

    public PolicyRecord activate(String policyId, String artifactId, String activatedBy, List<String> metrics) {
        long now = Instant.now().toEpochMilli();
        PolicyRecord record = new PolicyRecord(
            normalize(policyId),
            "pol_" + UUID.randomUUID().toString().replace("-", ""),
            normalize(artifactId),
            "ACTIVE",
            normalize(activatedBy),
            now,
            now,
            metrics == null ? List.of() : List.copyOf(metrics)
        );
        records.put(record.policyId(), record);
        activations.incrementAndGet();
        return record;
    }

    public PolicyRecord rollback(String policyId, String activatedBy) {
        PolicyRecord current = records.get(normalize(policyId));
        if (current == null) {
            return null;
        }
        PolicyRecord rolledBack = new PolicyRecord(
            current.policyId(),
            current.versionId(),
            current.artifactId(),
            "ROLLED_BACK",
            normalize(activatedBy),
            current.createdAt(),
            Instant.now().toEpochMilli(),
            current.metrics()
        );
        records.put(rolledBack.policyId(), rolledBack);
        rollbacks.incrementAndGet();
        return rolledBack;
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("policies", records.size());
        yaml.set("activations", activations.get());
        yaml.set("rollbacks", rollbacks.get());
        yaml.set("controls", Arrays.asList(
            "spawn_regulation",
            "drop_regulation",
            "economy_sink_faucet_control",
            "transfer_safety",
            "instance_allocation",
            "reward_idempotency",
            "anti_exploit_response",
            "experiment_admission",
            "queue_admission_control"
        ));
        Map<String, Object> active = new LinkedHashMap<>();
        for (PolicyRecord record : records.values()) {
            active.put(record.policyId(), Map.of(
                "version_id", record.versionId(),
                "artifact_id", record.artifactId(),
                "state", record.state(),
                "activated_by", record.activatedBy(),
                "metrics", record.metrics()
            ));
        }
        yaml.set("records", active);
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
