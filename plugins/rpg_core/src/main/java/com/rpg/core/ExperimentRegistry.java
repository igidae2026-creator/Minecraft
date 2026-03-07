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

public final class ExperimentRegistry {
    public enum ExperimentLifecycle {
        REGISTERED,
        CANARY,
        ACTIVE,
        KILLED,
        ROLLED_BACK,
        ARCHIVED
    }

    public record ExperimentRecord(
        String experimentId,
        String surface,
        String scope,
        String cohort,
        String artifactId,
        ExperimentLifecycle lifecycle,
        double safetyBudget,
        double anomalyScore,
        long createdAt,
        long updatedAt,
        List<String> mutationRefs
    ) {}

    private final ConcurrentMap<String, ExperimentRecord> records = new ConcurrentHashMap<>();
    private final AtomicLong rollbacks = new AtomicLong();
    private final AtomicLong kills = new AtomicLong();
    private final AtomicLong anomalyDetections = new AtomicLong();

    public ExperimentRecord register(String surface, String scope, String cohort, String artifactId, double safetyBudget) {
        long now = Instant.now().toEpochMilli();
        ExperimentRecord record = new ExperimentRecord(
            "exp_" + UUID.randomUUID().toString().replace("-", ""),
            normalize(surface),
            normalize(scope),
            normalize(cohort),
            normalize(artifactId),
            ExperimentLifecycle.REGISTERED,
            Math.max(0.0D, safetyBudget),
            0.0D,
            now,
            now,
            List.of()
        );
        records.put(record.experimentId(), record);
        return record;
    }

    public ExperimentRecord transition(String experimentId, ExperimentLifecycle lifecycle, double anomalyScore, List<String> mutationRefs) {
        ExperimentRecord current = records.get(experimentId);
        if (current == null) {
            return null;
        }
        if (lifecycle == ExperimentLifecycle.ROLLED_BACK) {
            rollbacks.incrementAndGet();
        }
        if (lifecycle == ExperimentLifecycle.KILLED) {
            kills.incrementAndGet();
        }
        if (anomalyScore > 0.0D) {
            anomalyDetections.incrementAndGet();
        }
        ExperimentRecord next = new ExperimentRecord(
            current.experimentId(),
            current.surface(),
            current.scope(),
            current.cohort(),
            current.artifactId(),
            lifecycle,
            current.safetyBudget(),
            Math.max(current.anomalyScore(), anomalyScore),
            current.createdAt(),
            Instant.now().toEpochMilli(),
            mutationRefs == null ? current.mutationRefs() : new ArrayList<>(mutationRefs)
        );
        records.put(experimentId, next);
        return next;
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("experiments", records.size());
        yaml.set("lifecycles", Arrays.stream(ExperimentLifecycle.values()).map(Enum::name).toList());
        yaml.set("rollbacks", rollbacks.get());
        yaml.set("kills", kills.get());
        yaml.set("anomaly_detections", anomalyDetections.get());
        Map<String, Object> active = new LinkedHashMap<>();
        for (ExperimentRecord record : records.values()) {
            active.put(record.experimentId(), Map.of(
                "surface", record.surface(),
                "scope", record.scope(),
                "cohort", record.cohort(),
                "lifecycle", record.lifecycle().name(),
                "artifact_id", record.artifactId(),
                "safety_budget", record.safetyBudget(),
                "anomaly_score", record.anomalyScore()
            ));
        }
        yaml.set("records", active);
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
