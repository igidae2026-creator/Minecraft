package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

public final class RuntimeKnowledgeIndex {
    public record KnowledgeRecord(
        String id,
        String classId,
        String scope,
        String artifactId,
        String lineageParent,
        double usefulness,
        long createdAt,
        List<String> tags
    ) {}

    private final ConcurrentMap<String, KnowledgeRecord> records = new ConcurrentHashMap<>();
    private final AtomicLong retrievals = new AtomicLong();

    public void remember(String id, String classId, String scope, String artifactId, String lineageParent, double usefulness, List<String> tags) {
        records.put(normalize(id), new KnowledgeRecord(
            normalize(id),
            normalize(classId),
            normalize(scope),
            normalize(artifactId),
            normalize(lineageParent),
            Math.max(0.0D, usefulness),
            Instant.now().toEpochMilli(),
            tags == null ? List.of() : new ArrayList<>(tags)
        ));
    }

    public List<KnowledgeRecord> retrieveTop(String classId, String scope, int limit) {
        retrievals.incrementAndGet();
        return records.values().stream()
            .filter(record -> classId == null || classId.isBlank() || record.classId().equals(normalize(classId)))
            .filter(record -> scope == null || scope.isBlank() || record.scope().equals(normalize(scope)))
            .sorted(Comparator.comparingDouble(KnowledgeRecord::usefulness).reversed().thenComparingLong(KnowledgeRecord::createdAt).reversed())
            .limit(Math.max(1, limit))
            .toList();
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("records", records.size());
        yaml.set("retrievals", retrievals.get());
        Map<String, Object> byId = new LinkedHashMap<>();
        for (KnowledgeRecord record : retrieveTop("", "", Math.min(32, records.size() == 0 ? 1 : records.size()))) {
            byId.put(record.id(), Map.of(
                "class_id", record.classId(),
                "scope", record.scope(),
                "artifact_id", record.artifactId(),
                "lineage_parent", record.lineageParent(),
                "usefulness", record.usefulness(),
                "tags", record.tags()
            ));
        }
        yaml.set("top_records", byId);
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
