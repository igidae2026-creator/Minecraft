package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class GovernancePolicyRegistry {
    public record PolicyVersion(
        String policyId,
        String versionId,
        String artifactId,
        String state,
        String activatedBy,
        long activatedAt,
        long deactivatedAt,
        List<String> metrics
    ) {}

    private final ConcurrentMap<String, PolicyVersion> activePolicies = new ConcurrentHashMap<>();
    private final AtomicLong rollbacks = new AtomicLong();

    public PolicyVersion activate(String policyId, String artifactId, String activatedBy, List<String> metrics) {
        long now = Instant.now().toEpochMilli();
        PolicyVersion version = new PolicyVersion(
            normalize(policyId),
            "policy_version_" + UUID.randomUUID().toString().replace("-", ""),
            normalize(artifactId),
            "ACTIVE",
            normalize(activatedBy),
            now,
            0L,
            metrics == null ? List.of() : new ArrayList<>(metrics)
        );
        activePolicies.put(version.policyId(), version);
        return version;
    }

    public PolicyVersion rollback(String policyId, String activatedBy) {
        String key = normalize(policyId);
        PolicyVersion current = activePolicies.get(key);
        if (current == null) {
            return null;
        }
        PolicyVersion rolledBack = new PolicyVersion(
            current.policyId(),
            current.versionId(),
            current.artifactId(),
            "ROLLED_BACK",
            normalize(activatedBy),
            current.activatedAt(),
            Instant.now().toEpochMilli(),
            current.metrics()
        );
        activePolicies.put(key, rolledBack);
        rollbacks.incrementAndGet();
        return rolledBack;
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("active_policies", activePolicies.size());
        yaml.set("rollbacks", rollbacks.get());
        yaml.set("policy_controls", Arrays.asList(
            "spawn_regulation",
            "drop_regulation",
            "economy_sinks",
            "transfer_safety",
            "instance_allocation",
            "reward_idempotency",
            "anti_exploit_response",
            "experiment_admission"
        ));
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
