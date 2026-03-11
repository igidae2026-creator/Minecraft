package com.rpg.core;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class GenreRegistry {
    public record GenreDefinition(
        String genreId,
        String targetServer,
        String worldName,
        String entryId,
        String label,
        String description,
        boolean partyCompatible
    ) {}

    private final Map<String, GenreDefinition> genres = new LinkedHashMap<>();

    public GenreRegistry(YamlConfiguration config) {
        ConfigurationSection registry = config.getConfigurationSection("genre_registry");
        if (registry != null) {
            for (String key : registry.getKeys(false)) {
                genres.put(normalize(key), new GenreDefinition(
                    normalize(key),
                    normalize(registry.getString(key + ".server", "")),
                    normalize(registry.getString(key + ".world", "")),
                    normalize(registry.getString(key + ".entry", "")),
                    registry.getString(key + ".label", key),
                    registry.getString(key + ".description", ""),
                    registry.getBoolean(key + ".party_compatible", true)
                ));
            }
        }
    }

    public GenreDefinition byGenreId(String genreId) {
        return genreId == null ? null : genres.get(normalize(genreId));
    }

    public GenreDefinition byServer(String serverName) {
        String normalized = normalize(serverName);
        for (GenreDefinition definition : genres.values()) {
            if (definition.targetServer().equals(normalized)) {
                return definition;
            }
        }
        return null;
    }

    public List<GenreDefinition> all() {
        return new ArrayList<>(genres.values());
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("genres", genres.size());
        Map<String, Object> values = new LinkedHashMap<>();
        for (GenreDefinition definition : genres.values()) {
            values.put(definition.genreId(), Map.of(
                "server", definition.targetServer(),
                "world", definition.worldName(),
                "entry", definition.entryId(),
                "label", definition.label(),
                "description", definition.description(),
                "party_compatible", definition.partyCompatible()
            ));
        }
        yaml.set("genre_registry", values);
        return yaml;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
