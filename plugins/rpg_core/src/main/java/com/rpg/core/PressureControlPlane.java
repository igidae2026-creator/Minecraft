package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

public final class PressureControlPlane {
    public record PressureSnapshot(
        double novelty,
        double diversity,
        double efficiency,
        double repair,
        double domainShift,
        double queuePressure,
        double entityPressure,
        double authorityPressure,
        double reconciliationPressure,
        double experimentPressure,
        long capturedAt
    ) {
        public double composite() {
            return Math.min(1.0D, Math.max(0.0D,
                (novelty + diversity + efficiency + repair + domainShift + queuePressure + entityPressure + authorityPressure + reconciliationPressure + experimentPressure) / 10.0D));
        }
    }

    private volatile PressureSnapshot current = new PressureSnapshot(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, Instant.now().toEpochMilli());
    private final AtomicLong suppressions = new AtomicLong();
    private final AtomicLong repairPriorities = new AtomicLong();

    public PressureSnapshot update(double novelty, double diversity, double efficiency, double repair, double domainShift,
                                   double queuePressure, double entityPressure, double authorityPressure,
                                   double reconciliationPressure, double experimentPressure) {
        current = new PressureSnapshot(
            normalize(novelty),
            normalize(diversity),
            normalize(efficiency),
            normalize(repair),
            normalize(domainShift),
            normalize(queuePressure),
            normalize(entityPressure),
            normalize(authorityPressure),
            normalize(reconciliationPressure),
            normalize(experimentPressure),
            Instant.now().toEpochMilli()
        );
        if (current.composite() >= 0.75D) {
            suppressions.incrementAndGet();
        }
        if (current.repair() >= 0.60D || current.reconciliationPressure() >= 0.60D) {
            repairPriorities.incrementAndGet();
        }
        return current;
    }

    public PressureSnapshot current() {
        return current;
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("novelty", current.novelty());
        yaml.set("diversity", current.diversity());
        yaml.set("efficiency", current.efficiency());
        yaml.set("repair", current.repair());
        yaml.set("domain_shift", current.domainShift());
        yaml.set("queue_pressure", current.queuePressure());
        yaml.set("entity_pressure", current.entityPressure());
        yaml.set("authority_pressure", current.authorityPressure());
        yaml.set("reconciliation_pressure", current.reconciliationPressure());
        yaml.set("experiment_pressure", current.experimentPressure());
        yaml.set("composite", current.composite());
        yaml.set("captured_at", current.capturedAt());
        yaml.set("suppressions", suppressions.get());
        yaml.set("repair_priorities", repairPriorities.get());
        return yaml;
    }

    private double normalize(double value) {
        return Math.max(0.0D, Math.min(1.0D, value));
    }
}
