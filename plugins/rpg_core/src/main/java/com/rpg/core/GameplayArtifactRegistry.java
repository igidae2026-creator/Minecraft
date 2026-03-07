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

public final class GameplayArtifactRegistry {
    public enum ArtifactClass {
        LOOT_TABLE_VARIANT,
        DUNGEON_TOPOLOGY_VARIANT,
        BOSS_MECHANIC_VARIANT,
        ENCOUNTER_PACING_VARIANT,
        GEAR_PROGRESSION_VARIANT,
        QUEST_GRAPH_VARIANT,
        ECONOMY_PARAMETER_SET,
        SPAWN_DISTRIBUTION_VARIANT,
        PLAYER_STRATEGY_CLUSTER,
        BALANCING_DECISION,
        EXPLOIT_SIGNATURE,
        EXPERIMENT_DEFINITION,
        EXPERIMENT_RESULT,
        GOVERNANCE_DECISION,
        RECOVERY_ACTION,
        COMPENSATION_ACTION
    }

    public record ArtifactRecord(
        String artifactId,
        ArtifactClass artifactClass,
        String lineageParent,
        String generationMetadataRef,
        String evaluationMetadataRef,
        String selectionMetadataRef,
        List<String> mutationLineage,
        String archiveExportPath,
        double usefulnessScore,
        List<String> tags,
        long createdAt
    ) {}

    private final ConcurrentMap<String, ArtifactRecord> artifacts = new ConcurrentHashMap<>();

    public ArtifactRecord register(ArtifactClass artifactClass, String lineageParent, String generationMetadataRef,
                                   String evaluationMetadataRef, String selectionMetadataRef,
                                   List<String> mutationLineage, String archiveExportPath,
                                   double usefulnessScore, List<String> tags) {
        ArtifactRecord record = new ArtifactRecord(
            "artifact_" + UUID.randomUUID().toString().replace("-", ""),
            artifactClass,
            normalize(lineageParent),
            normalize(generationMetadataRef),
            normalize(evaluationMetadataRef),
            normalize(selectionMetadataRef),
            mutationLineage == null ? List.of() : new ArrayList<>(mutationLineage),
            archiveExportPath == null ? "" : archiveExportPath,
            Math.max(0.0D, usefulnessScore),
            tags == null ? List.of() : new ArrayList<>(tags),
            Instant.now().toEpochMilli()
        );
        artifacts.put(record.artifactId(), record);
        return record;
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("artifact_total", artifacts.size());
        yaml.set("artifact_classes", Arrays.stream(ArtifactClass.values()).map(Enum::name).toList());
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (ArtifactRecord artifact : artifacts.values()) {
            counts.merge(artifact.artifactClass().name().toLowerCase(Locale.ROOT), 1, Integer::sum);
        }
        yaml.set("counts", counts);
        yaml.set("top_useful", artifacts.values().stream()
            .sorted((left, right) -> Double.compare(right.usefulnessScore(), left.usefulnessScore()))
            .limit(16)
            .map(artifact -> Map.of(
                "artifact_id", artifact.artifactId(),
                "class", artifact.artifactClass().name(),
                "usefulness", artifact.usefulnessScore(),
                "archive_export_path", artifact.archiveExportPath(),
                "tags", artifact.tags()
            ))
            .toList());
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
