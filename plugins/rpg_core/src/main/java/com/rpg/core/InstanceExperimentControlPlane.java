package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class InstanceExperimentControlPlane {
    public enum RuntimeInstanceClass {
        DUNGEON_INSTANCE,
        BOSS_ENCOUNTER_INSTANCE,
        EVENT_INSTANCE,
        EXPLORATION_SANDBOX_INSTANCE
    }

    public enum RuntimeInstanceState {
        REQUESTED,
        ALLOCATING,
        BOOTING,
        READY,
        ACTIVE,
        RESOLVING,
        REWARD_COMMIT,
        EGRESS,
        CLEANUP,
        TERMINATED,
        FAILED,
        ORPHANED,
        DEGRADED
    }

    public enum ExperimentState {
        REGISTERED,
        CANARY,
        ACTIVE,
        ROLLED_BACK,
        ARCHIVED
    }

    public record RuntimeInstance(String id, RuntimeInstanceClass type, RuntimeInstanceState state,
                                  String ownerRef, String policyVersion, String experimentId,
                                  long createdAt, long updatedAt, long expiresAt) {}

    public record ExperimentDefinition(String id, String name, String surface, String segment,
                                       String artifactId, ExperimentState state, double rollbackThreshold,
                                       long createdAt, long updatedAt) {}

    public record PolicyVersion(String policyId, String versionId, String status,
                                String artifactId, long activatedAt, long deactivatedAt) {}

    private final ConcurrentMap<String, RuntimeInstance> instances = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, ExperimentDefinition> experiments = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, PolicyVersion> activePolicies = new ConcurrentHashMap<>();

    private final AtomicLong orphanRecovered = new AtomicLong();
    private final AtomicLong cleanupRuns = new AtomicLong();
    private final AtomicLong policyRollbacks = new AtomicLong();
    private final AtomicLong experimentRollbacks = new AtomicLong();
    private final AtomicLong degradations = new AtomicLong();

    public RuntimeInstance registerInstance(RuntimeInstanceClass type, String ownerRef, String policyVersion,
                                            String experimentId, long ttlMillis) {
        long now = Instant.now().toEpochMilli();
        RuntimeInstance created = new RuntimeInstance(
            "inst_" + UUID.randomUUID().toString().replace("-", ""),
            type,
            RuntimeInstanceState.REQUESTED,
            normalize(ownerRef),
            normalize(policyVersion),
            normalize(experimentId),
            now,
            now,
            now + Math.max(ttlMillis, 60_000L)
        );
        instances.put(created.id(), created);
        return created;
    }

    public RuntimeInstance transition(String instanceId, RuntimeInstanceState nextState) {
        RuntimeInstance current = instances.get(instanceId);
        if (current == null) {
            return null;
        }
        if (nextState == RuntimeInstanceState.DEGRADED) {
            degradations.incrementAndGet();
        }
        RuntimeInstance next = new RuntimeInstance(current.id(), current.type(), nextState, current.ownerRef(),
            current.policyVersion(), current.experimentId(), current.createdAt(), Instant.now().toEpochMilli(), current.expiresAt());
        instances.put(instanceId, next);
        return next;
    }

    public int recoverOrphans(long now) {
        int recovered = 0;
        for (RuntimeInstance instance : new ArrayList<>(instances.values())) {
            if (instance.expiresAt() <= now && instance.state() != RuntimeInstanceState.TERMINATED) {
                instances.put(instance.id(), new RuntimeInstance(instance.id(), instance.type(), RuntimeInstanceState.ORPHANED,
                    instance.ownerRef(), instance.policyVersion(), instance.experimentId(), instance.createdAt(), now, instance.expiresAt()));
                orphanRecovered.incrementAndGet();
                recovered++;
            }
        }
        return recovered;
    }

    public int sweepTerminated() {
        int removed = 0;
        for (RuntimeInstance instance : new ArrayList<>(instances.values())) {
            if (instance.state() == RuntimeInstanceState.TERMINATED || instance.state() == RuntimeInstanceState.ORPHANED) {
                instances.remove(instance.id());
                removed++;
            }
        }
        cleanupRuns.incrementAndGet();
        return removed;
    }

    public ExperimentDefinition registerExperiment(String name, String surface, String segment,
                                                   String artifactId, double rollbackThreshold) {
        long now = Instant.now().toEpochMilli();
        ExperimentDefinition definition = new ExperimentDefinition(
            "exp_" + UUID.randomUUID().toString().replace("-", ""),
            normalize(name),
            normalize(surface),
            normalize(segment),
            normalize(artifactId),
            ExperimentState.REGISTERED,
            rollbackThreshold,
            now,
            now
        );
        experiments.put(definition.id(), definition);
        return definition;
    }

    public void rollbackExperiment(String experimentId) {
        ExperimentDefinition current = experiments.get(experimentId);
        if (current == null) {
            return;
        }
        experiments.put(experimentId, new ExperimentDefinition(current.id(), current.name(), current.surface(), current.segment(),
            current.artifactId(), ExperimentState.ROLLED_BACK, current.rollbackThreshold(), current.createdAt(), Instant.now().toEpochMilli()));
        experimentRollbacks.incrementAndGet();
    }

    public void activatePolicy(String policyId, String versionId, String artifactId) {
        activePolicies.put(normalize(policyId), new PolicyVersion(normalize(policyId), normalize(versionId), "ACTIVE",
            normalize(artifactId), Instant.now().toEpochMilli(), 0L));
    }

    public void rollbackPolicy(String policyId) {
        String key = normalize(policyId);
        PolicyVersion current = activePolicies.get(key);
        if (current == null) {
            return;
        }
        activePolicies.put(key, new PolicyVersion(current.policyId(), current.versionId(), "ROLLED_BACK", current.artifactId(),
            current.activatedAt(), Instant.now().toEpochMilli()));
        policyRollbacks.incrementAndGet();
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("active_instances", instances.size());
        yaml.set("experiments", experiments.size());
        yaml.set("active_policies", activePolicies.size());
        yaml.set("orphan_recovered", orphanRecovered.get());
        yaml.set("cleanup_runs", cleanupRuns.get());
        yaml.set("policy_rollbacks", policyRollbacks.get());
        yaml.set("experiment_rollbacks", experimentRollbacks.get());
        yaml.set("degradations", degradations.get());
        yaml.set("instance_types", Arrays.stream(RuntimeInstanceClass.values()).map(Enum::name).toList());
        yaml.set("instance_states", Arrays.stream(RuntimeInstanceState.values()).map(Enum::name).toList());
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
