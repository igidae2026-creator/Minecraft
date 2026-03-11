package com.rpg.core;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ThreadLocalRandom;

public final class ContentEngine {
    public record DungeonTemplate(
        String templateId,
        String layoutType,
        List<String> enemyGroups,
        String bossType,
        String rewardTier,
        double difficultyScaling,
        int recommendedPartySize,
        int playerCap
    ) {}

    public record BossPhase(
        String phaseId,
        double healthThreshold,
        List<String> abilities
    ) {}

    public record BossBehavior(
        String bossId,
        int tickInterval,
        List<BossPhase> phases,
        double enragedThreshold,
        double groupScaling
    ) {}

    public record ScheduledEvent(
        String eventId,
        String eventType,
        int weight,
        int cooldownMinutes,
        String linkedRewardPool
    ) {}

    public record RewardPool(
        String poolId,
        Map<String, Integer> guaranteedItems,
        Map<String, Double> weightedItems,
        int guaranteedProgressionCurrency,
        int guaranteedGenreCurrency,
        double guaranteedGold,
        List<String> milestoneRewards
    ) {}

    public record RewardBundle(
        Map<String, Integer> items,
        int progressionCurrency,
        int genreCurrency,
        double gold,
        List<String> milestones
    ) {}

    private final ConcurrentMap<String, String> activeDungeonTemplates = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, Long> schedulerHistory = new ConcurrentHashMap<>();
    private final Map<String, DungeonTemplate> dungeonTemplates = new LinkedHashMap<>();
    private final Map<String, BossBehavior> bossBehaviors = new LinkedHashMap<>();
    private final Map<String, ScheduledEvent> scheduledEvents = new LinkedHashMap<>();
    private final Map<String, RewardPool> rewardPools = new LinkedHashMap<>();

    public ContentEngine(YamlConfiguration dungeonTemplatesConfig, YamlConfiguration bossBehaviorsConfig,
                         YamlConfiguration schedulerConfig, YamlConfiguration rewardPoolsConfig) {
        loadDungeonTemplates(dungeonTemplatesConfig);
        loadBossBehaviors(bossBehaviorsConfig);
        loadScheduledEvents(schedulerConfig);
        loadRewardPools(rewardPoolsConfig);
    }

    public DungeonTemplate resolveDungeonTemplate(String dungeonId, String configuredTemplateId) {
        String active = activeDungeonTemplates.getOrDefault(normalize(dungeonId), normalize(configuredTemplateId));
        DungeonTemplate resolved = dungeonTemplates.get(active);
        if (resolved != null) {
            return resolved;
        }
        if (configuredTemplateId != null && !configuredTemplateId.isBlank()) {
            return dungeonTemplates.get(normalize(configuredTemplateId));
        }
        return dungeonTemplates.values().stream().findFirst().orElse(null);
    }

    public void activateDungeonTemplate(String dungeonId, String templateId) {
        if (dungeonId == null || dungeonId.isBlank() || templateId == null || templateId.isBlank()) {
            return;
        }
        activeDungeonTemplates.put(normalize(dungeonId), normalize(templateId));
    }

    public BossBehavior bossBehavior(String bossId) {
        return bossBehaviors.get(normalize(bossId));
    }

    public ScheduledEvent scheduledEvent(String eventId) {
        return scheduledEvents.get(normalize(eventId));
    }

    public ScheduledEvent nextEvent(String currentEventId, long now) {
        return scheduledEvents.values().stream()
            .filter(event -> !event.eventId().equalsIgnoreCase(normalize(currentEventId)))
            .filter(event -> now - schedulerHistory.getOrDefault(event.eventId(), 0L) >= event.cooldownMinutes() * 60_000L)
            .max(Comparator.comparingInt(ScheduledEvent::weight))
            .orElseGet(() -> scheduledEvents.values().stream().findFirst().orElse(null));
    }

    public void markEventStarted(String eventId, long now) {
        if (eventId != null && !eventId.isBlank()) {
            schedulerHistory.put(normalize(eventId), now);
        }
    }

    public RewardBundle composeRewards(String poolId, double difficultyScale) {
        RewardPool pool = rewardPools.get(normalize(poolId));
        if (pool == null) {
            return new RewardBundle(Map.of(), 0, 0, 0.0D, List.of());
        }
        Map<String, Integer> items = new LinkedHashMap<>(pool.guaranteedItems());
        for (Map.Entry<String, Double> entry : pool.weightedItems().entrySet()) {
            double chance = Math.max(0.0D, Math.min(1.0D, entry.getValue() * Math.max(0.5D, difficultyScale)));
            if (ThreadLocalRandom.current().nextDouble() <= chance) {
                items.merge(entry.getKey(), 1, Integer::sum);
            }
        }
        int progression = Math.max(0, (int) Math.round(pool.guaranteedProgressionCurrency() * Math.max(0.5D, difficultyScale)));
        int genre = Math.max(0, (int) Math.round(pool.guaranteedGenreCurrency() * Math.max(0.5D, difficultyScale)));
        double gold = Math.max(0.0D, pool.guaranteedGold() * Math.max(0.5D, difficultyScale));
        return new RewardBundle(items, progression, genre, gold, new ArrayList<>(pool.milestoneRewards()));
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("dungeon_templates", dungeonTemplates.keySet().stream().sorted().toList());
        yaml.set("boss_behaviors", bossBehaviors.keySet().stream().sorted().toList());
        yaml.set("scheduled_events", scheduledEvents.keySet().stream().sorted().toList());
        yaml.set("reward_pools", rewardPools.keySet().stream().sorted().toList());
        yaml.set("active_dungeon_templates", new LinkedHashMap<>(activeDungeonTemplates));
        return yaml;
    }

    private void loadDungeonTemplates(YamlConfiguration config) {
        ConfigurationSection section = config.getConfigurationSection("templates");
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            dungeonTemplates.put(normalize(key), new DungeonTemplate(
                normalize(key),
                normalize(section.getString(key + ".layout_type", "arena")),
                new ArrayList<>(section.getStringList(key + ".enemy_groups")),
                normalize(section.getString(key + ".boss_type", "")),
                normalize(section.getString(key + ".reward_tier", "starter")),
                Math.max(0.5D, section.getDouble(key + ".difficulty_scaling", 1.0D)),
                Math.max(1, section.getInt(key + ".recommended_party_size", 1)),
                Math.max(1, section.getInt(key + ".player_cap", section.getInt(key + ".recommended_party_size", 1)))
            ));
        }
    }

    private void loadBossBehaviors(YamlConfiguration config) {
        ConfigurationSection section = config.getConfigurationSection("behaviors");
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            List<BossPhase> phases = new ArrayList<>();
            ConfigurationSection phaseSection = section.getConfigurationSection(key + ".phases");
            if (phaseSection != null) {
                for (String phaseId : phaseSection.getKeys(false)) {
                    phases.add(new BossPhase(
                        normalize(phaseId),
                        Math.max(0.0D, Math.min(1.0D, phaseSection.getDouble(phaseId + ".health_threshold", 1.0D))),
                        new ArrayList<>(phaseSection.getStringList(phaseId + ".abilities"))
                    ));
                }
                phases.sort(Comparator.comparingDouble(BossPhase::healthThreshold).reversed());
            }
            bossBehaviors.put(normalize(key), new BossBehavior(
                normalize(key),
                Math.max(20, section.getInt(key + ".tick_interval", 60)),
                phases,
                Math.max(0.0D, Math.min(1.0D, section.getDouble(key + ".enraged_threshold", 0.20D))),
                Math.max(0.0D, section.getDouble(key + ".group_scaling", 0.15D))
            ));
        }
    }

    private void loadScheduledEvents(YamlConfiguration config) {
        ConfigurationSection section = config.getConfigurationSection("events");
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            scheduledEvents.put(normalize(key), new ScheduledEvent(
                normalize(key),
                normalize(section.getString(key + ".type", "timed_invasion")),
                Math.max(1, section.getInt(key + ".weight", 1)),
                Math.max(1, section.getInt(key + ".cooldown_minutes", 30)),
                normalize(section.getString(key + ".reward_pool", "starter"))
            ));
        }
    }

    private void loadRewardPools(YamlConfiguration config) {
        ConfigurationSection section = config.getConfigurationSection("pools");
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            Map<String, Integer> guaranteed = new LinkedHashMap<>();
            ConfigurationSection guaranteedSection = section.getConfigurationSection(key + ".guaranteed_items");
            if (guaranteedSection != null) {
                for (String itemId : guaranteedSection.getKeys(false)) {
                    guaranteed.put(normalize(itemId), guaranteedSection.getInt(itemId, 0));
                }
            }
            Map<String, Double> weighted = new LinkedHashMap<>();
            ConfigurationSection weightedSection = section.getConfigurationSection(key + ".weighted_items");
            if (weightedSection != null) {
                for (String itemId : weightedSection.getKeys(false)) {
                    weighted.put(normalize(itemId), weightedSection.getDouble(itemId, 0.0D));
                }
            }
            rewardPools.put(normalize(key), new RewardPool(
                normalize(key),
                guaranteed,
                weighted,
                Math.max(0, section.getInt(key + ".progression_currency", 0)),
                Math.max(0, section.getInt(key + ".genre_currency", 0)),
                Math.max(0.0D, section.getDouble(key + ".gold", 0.0D)),
                new ArrayList<>(section.getStringList(key + ".milestone_rewards"))
            ));
        }
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
