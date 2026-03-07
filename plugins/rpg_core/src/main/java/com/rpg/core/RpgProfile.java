package com.rpg.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

public final class RpgProfile {
    private final UUID uuid;
    private String lastName;
    private double gold;
    private final Map<String, Integer> inventory = new LinkedHashMap<>();
    private final Map<String, String> gearTiers = new LinkedHashMap<>();
    private final Map<String, Double> skillXp = new LinkedHashMap<>();
    private final Set<String> acceptedQuests = new LinkedHashSet<>();
    private final Map<String, Integer> questProgress = new LinkedHashMap<>();
    private final Set<String> completedQuests = new LinkedHashSet<>();
    private final Map<String, Long> questCooldowns = new LinkedHashMap<>();
    private String activeDungeon = "";
    private String activeDungeonInstanceId = "";
    private String activeDungeonWorld = "";
    private int activeDungeonKills;
    private boolean activeDungeonBossSpawned;
    private long activeDungeonStartedAt;
    private final Map<String, Long> dungeonCooldowns = new LinkedHashMap<>();
    private final Map<String, Long> bossLockouts = new LinkedHashMap<>();
    private final Map<String, String> bossDailyBonusDate = new LinkedHashMap<>();
    private String guildName = "";
    private final Map<String, Long> processedNonces = new LinkedHashMap<>();
    private final Map<String, Long> claimedOperations = new LinkedHashMap<>();
    private final Map<String, Integer> killCounts = new LinkedHashMap<>();
    private double totalGoldEarned;
    private double totalGoldSpent;
    private int transfers;
    private long createdAt;
    private long updatedAt;
    private long lastJoinAt;
    private long lastQuitAt;

    public RpgProfile(UUID uuid, String lastName) {
        this.uuid = uuid;
        this.lastName = lastName;
        long now = System.currentTimeMillis();
        this.createdAt = now;
        this.updatedAt = now;
    }

    public static RpgProfile fromYaml(UUID uuid, String defaultName, YamlConfiguration yaml) {
        RpgProfile profile = new RpgProfile(uuid, yaml.getString("last_name", defaultName));
        profile.gold = yaml.getDouble("gold", 0.0D);
        profile.createdAt = yaml.getLong("created_at", System.currentTimeMillis());
        profile.updatedAt = yaml.getLong("updated_at", profile.createdAt);
        profile.lastJoinAt = yaml.getLong("last_join_at", 0L);
        profile.lastQuitAt = yaml.getLong("last_quit_at", 0L);
        profile.totalGoldEarned = yaml.getDouble("stats.total_gold_earned", 0.0D);
        profile.totalGoldSpent = yaml.getDouble("stats.total_gold_spent", 0.0D);
        profile.transfers = yaml.getInt("stats.transfers", 0);
        profile.activeDungeon = yaml.getString("dungeons.active.id", "");
        profile.activeDungeonInstanceId = yaml.getString("dungeons.active.instance_id", "");
        profile.activeDungeonWorld = yaml.getString("dungeons.active.world", "");
        profile.activeDungeonKills = yaml.getInt("dungeons.active.kills", 0);
        profile.activeDungeonBossSpawned = yaml.getBoolean("dungeons.active.boss_spawned", false);
        profile.activeDungeonStartedAt = yaml.getLong("dungeons.active.started_at", 0L);
        profile.guildName = yaml.getString("guild.name", "");

        loadIntMap(yaml.getConfigurationSection("inventory"), profile.inventory);
        loadStringMap(yaml.getConfigurationSection("gear"), profile.gearTiers);
        loadDoubleMap(yaml.getConfigurationSection("skills_xp"), profile.skillXp);
        loadStringSet(yaml.getConfigurationSection("quests.accepted"), profile.acceptedQuests);
        loadIntMap(yaml.getConfigurationSection("quests.progress"), profile.questProgress);
        profile.completedQuests.addAll(yaml.getStringList("quests.completed"));
        loadLongMap(yaml.getConfigurationSection("quests.cooldowns"), profile.questCooldowns);
        loadLongMap(yaml.getConfigurationSection("dungeons.cooldowns"), profile.dungeonCooldowns);
        loadLongMap(yaml.getConfigurationSection("bosses.lockouts"), profile.bossLockouts);
        loadStringMap(yaml.getConfigurationSection("bosses.daily_bonus_date"), profile.bossDailyBonusDate);
        loadLongMap(yaml.getConfigurationSection("nonces"), profile.processedNonces);
        loadLongMap(yaml.getConfigurationSection("claims"), profile.claimedOperations);
        loadIntMap(yaml.getConfigurationSection("stats.kills"), profile.killCounts);

        if (profile.lastName == null || profile.lastName.isBlank()) {
            profile.lastName = defaultName;
        }
        return profile;
    }

    public YamlConfiguration toYaml() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("uuid", uuid.toString());
        yaml.set("last_name", lastName);
        yaml.set("gold", gold);
        yaml.set("created_at", createdAt);
        yaml.set("updated_at", updatedAt);
        yaml.set("last_join_at", lastJoinAt);
        yaml.set("last_quit_at", lastQuitAt);
        yaml.set("inventory", new LinkedHashMap<>(inventory));
        yaml.set("gear", new LinkedHashMap<>(gearTiers));
        yaml.set("skills_xp", new LinkedHashMap<>(skillXp));
        yaml.set("quests.accepted", keySetToSection(acceptedQuests));
        yaml.set("quests.progress", new LinkedHashMap<>(questProgress));
        yaml.set("quests.completed", new ArrayList<>(completedQuests));
        yaml.set("quests.cooldowns", new LinkedHashMap<>(questCooldowns));
        yaml.set("dungeons.active.id", activeDungeon);
        yaml.set("dungeons.active.instance_id", activeDungeonInstanceId);
        yaml.set("dungeons.active.world", activeDungeonWorld);
        yaml.set("dungeons.active.kills", activeDungeonKills);
        yaml.set("dungeons.active.boss_spawned", activeDungeonBossSpawned);
        yaml.set("dungeons.active.started_at", activeDungeonStartedAt);
        yaml.set("dungeons.cooldowns", new LinkedHashMap<>(dungeonCooldowns));
        yaml.set("bosses.lockouts", new LinkedHashMap<>(bossLockouts));
        yaml.set("bosses.daily_bonus_date", new LinkedHashMap<>(bossDailyBonusDate));
        yaml.set("guild.name", guildName);
        yaml.set("nonces", new LinkedHashMap<>(processedNonces));
        yaml.set("claims", new LinkedHashMap<>(claimedOperations));
        yaml.set("stats.kills", new LinkedHashMap<>(killCounts));
        yaml.set("stats.total_gold_earned", totalGoldEarned);
        yaml.set("stats.total_gold_spent", totalGoldSpent);
        yaml.set("stats.transfers", transfers);
        return yaml;
    }

    private static Map<String, Boolean> keySetToSection(Set<String> keys) {
        Map<String, Boolean> section = new LinkedHashMap<>();
        for (String key : keys) {
            section.put(key, Boolean.TRUE);
        }
        return section;
    }

    private static void loadIntMap(ConfigurationSection section, Map<String, Integer> out) {
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            out.put(key, Math.max(0, section.getInt(key, 0)));
        }
    }

    private static void loadLongMap(ConfigurationSection section, Map<String, Long> out) {
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            out.put(key, section.getLong(key, 0L));
        }
    }

    private static void loadStringMap(ConfigurationSection section, Map<String, String> out) {
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            out.put(key, section.getString(key, ""));
        }
    }

    private static void loadDoubleMap(ConfigurationSection section, Map<String, Double> out) {
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            out.put(key, section.getDouble(key, 0.0D));
        }
    }

    private static void loadStringSet(ConfigurationSection section, Set<String> out) {
        if (section == null) {
            return;
        }
        out.addAll(section.getKeys(false));
    }

    public UUID getUuid() {
        return uuid;
    }

    public String getLastName() {
        return lastName;
    }

    public void touch(String latestName) {
        if (latestName != null && !latestName.isBlank() && !latestName.equals(this.lastName)) {
            this.lastName = latestName;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public double getGold() {
        return gold;
    }

    public void setGold(double gold) {
        double next = Math.max(0.0D, gold);
        if (Double.compare(this.gold, next) != 0) {
            this.gold = next;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public void addGold(double amount) {
        if (amount <= 0.0D) {
            return;
        }
        this.gold += amount;
        this.totalGoldEarned += amount;
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean spendGold(double amount) {
        if (amount <= 0.0D) {
            return true;
        }
        if (gold + 0.000001D < amount) {
            return false;
        }
        this.gold -= amount;
        this.totalGoldSpent += amount;
        this.updatedAt = System.currentTimeMillis();
        return true;
    }

    public void incrementTransfers() {
        this.transfers += 1;
        this.updatedAt = System.currentTimeMillis();
    }

    public int getTransfers() {
        return transfers;
    }

    public Map<String, Integer> getInventoryView() {
        return Collections.unmodifiableMap(inventory);
    }

    public int getItemCount(String itemId) {
        return inventory.getOrDefault(itemId.toLowerCase(Locale.ROOT), 0);
    }

    public void addItem(String itemId, int amount) {
        if (itemId == null || itemId.isBlank() || amount <= 0) {
            return;
        }
        String key = itemId.toLowerCase(Locale.ROOT);
        inventory.put(key, getItemCount(key) + amount);
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean removeItem(String itemId, int amount) {
        if (amount <= 0) {
            return true;
        }
        String key = itemId.toLowerCase(Locale.ROOT);
        int current = getItemCount(key);
        if (current < amount) {
            return false;
        }
        int next = current - amount;
        if (next <= 0) {
            inventory.remove(key);
        } else {
            inventory.put(key, next);
        }
        this.updatedAt = System.currentTimeMillis();
        return true;
    }

    public boolean hasItems(Map<String, Integer> required) {
        for (Map.Entry<String, Integer> entry : required.entrySet()) {
            if (getItemCount(entry.getKey()) < entry.getValue()) {
                return false;
            }
        }
        return true;
    }

    public Map<String, String> getGearTiersView() {
        return Collections.unmodifiableMap(gearTiers);
    }

    public String getGearTier(String gearPath, String fallback) {
        return gearTiers.getOrDefault(gearPath, fallback);
    }

    public void setGearTier(String gearPath, String tier) {
        if (gearPath == null || gearPath.isBlank() || tier == null || tier.isBlank()) {
            return;
        }
        if (!tier.equals(gearTiers.get(gearPath))) {
            gearTiers.put(gearPath, tier);
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public void ensureGearTier(String gearPath, String defaultTier) {
        if (!gearTiers.containsKey(gearPath)) {
            gearTiers.put(gearPath, defaultTier);
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public double getSkillXp(String skill) {
        return skillXp.getOrDefault(skill.toLowerCase(Locale.ROOT), 0.0D);
    }

    public Map<String, Double> getSkillXpView() {
        return Collections.unmodifiableMap(skillXp);
    }

    public void addSkillXp(String skill, double amount) {
        if (skill == null || skill.isBlank() || amount <= 0.0D) {
            return;
        }
        String key = skill.toLowerCase(Locale.ROOT);
        skillXp.put(key, getSkillXp(key) + amount);
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean isQuestAccepted(String questId) {
        return acceptedQuests.contains(questId);
    }

    public Set<String> getAcceptedQuestsView() {
        return Collections.unmodifiableSet(acceptedQuests);
    }

    public void acceptQuest(String questId) {
        acceptedQuests.add(questId);
        questProgress.putIfAbsent(questId, 0);
        this.updatedAt = System.currentTimeMillis();
    }

    public void abandonQuest(String questId) {
        acceptedQuests.remove(questId);
        questProgress.remove(questId);
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean isQuestCompleted(String questId) {
        return completedQuests.contains(questId);
    }

    public Set<String> getCompletedQuestsView() {
        return Collections.unmodifiableSet(completedQuests);
    }

    public void markQuestCompleted(String questId) {
        completedQuests.add(questId);
        this.updatedAt = System.currentTimeMillis();
    }

    public int getQuestProgress(String questId) {
        return questProgress.getOrDefault(questId, 0);
    }

    public void setQuestProgress(String questId, int progress) {
        int next = Math.max(0, progress);
        if (questProgress.getOrDefault(questId, 0) != next) {
            questProgress.put(questId, next);
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public long getQuestCooldown(String questId) {
        return questCooldowns.getOrDefault(questId, 0L);
    }

    public void setQuestCooldown(String questId, long expiresAtMillis) {
        questCooldowns.put(questId, expiresAtMillis);
        this.updatedAt = System.currentTimeMillis();
    }

    public String getActiveDungeon() {
        return activeDungeon;
    }

    public void setActiveDungeon(String activeDungeon) {
        String next = activeDungeon == null ? "" : activeDungeon;
        if (!next.equals(this.activeDungeon)) {
            this.activeDungeon = next;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public String getActiveDungeonInstanceId() {
        return activeDungeonInstanceId;
    }

    public void setActiveDungeonInstanceId(String activeDungeonInstanceId) {
        String next = activeDungeonInstanceId == null ? "" : activeDungeonInstanceId;
        if (!next.equals(this.activeDungeonInstanceId)) {
            this.activeDungeonInstanceId = next;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public String getActiveDungeonWorld() {
        return activeDungeonWorld;
    }

    public void setActiveDungeonWorld(String activeDungeonWorld) {
        String next = activeDungeonWorld == null ? "" : activeDungeonWorld;
        if (!next.equals(this.activeDungeonWorld)) {
            this.activeDungeonWorld = next;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public int getActiveDungeonKills() {
        return activeDungeonKills;
    }

    public void setActiveDungeonKills(int activeDungeonKills) {
        int next = Math.max(0, activeDungeonKills);
        if (this.activeDungeonKills != next) {
            this.activeDungeonKills = next;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public void incrementActiveDungeonKills() {
        this.activeDungeonKills += 1;
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean isActiveDungeonBossSpawned() {
        return activeDungeonBossSpawned;
    }

    public void setActiveDungeonBossSpawned(boolean activeDungeonBossSpawned) {
        if (this.activeDungeonBossSpawned != activeDungeonBossSpawned) {
            this.activeDungeonBossSpawned = activeDungeonBossSpawned;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public long getActiveDungeonStartedAt() {
        return activeDungeonStartedAt;
    }

    public void setActiveDungeonStartedAt(long activeDungeonStartedAt) {
        if (this.activeDungeonStartedAt != activeDungeonStartedAt) {
            this.activeDungeonStartedAt = activeDungeonStartedAt;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public void clearActiveDungeon() {
        this.activeDungeon = "";
        this.activeDungeonInstanceId = "";
        this.activeDungeonWorld = "";
        this.activeDungeonKills = 0;
        this.activeDungeonBossSpawned = false;
        this.activeDungeonStartedAt = 0L;
        this.updatedAt = System.currentTimeMillis();
    }

    public long getDungeonCooldown(String dungeonId) {
        return dungeonCooldowns.getOrDefault(dungeonId, 0L);
    }

    public void setDungeonCooldown(String dungeonId, long expiresAtMillis) {
        dungeonCooldowns.put(dungeonId, expiresAtMillis);
        this.updatedAt = System.currentTimeMillis();
    }

    public long getBossLockout(String bossId) {
        return bossLockouts.getOrDefault(bossId, 0L);
    }

    public void setBossLockout(String bossId, long expiresAtMillis) {
        bossLockouts.put(bossId, expiresAtMillis);
        this.updatedAt = System.currentTimeMillis();
    }

    public String getBossDailyBonusDate(String bossId) {
        return bossDailyBonusDate.getOrDefault(bossId, "");
    }

    public void setBossDailyBonusDate(String bossId, String dateKey) {
        bossDailyBonusDate.put(bossId, dateKey);
        this.updatedAt = System.currentTimeMillis();
    }

    public String getGuildName() {
        return guildName;
    }

    public void setGuildName(String guildName) {
        String next = guildName == null ? "" : guildName;
        if (!next.equals(this.guildName)) {
            this.guildName = next;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public Map<String, Integer> getKillCountsView() {
        return Collections.unmodifiableMap(killCounts);
    }

    public void incrementKillCount(String targetId) {
        killCounts.put(targetId, killCounts.getOrDefault(targetId, 0) + 1);
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean isNonceSeen(String nonce, long windowMillis) {
        pruneNonces(windowMillis);
        return processedNonces.containsKey(nonce);
    }

    public void markNonce(String nonce) {
        processedNonces.put(nonce, System.currentTimeMillis());
        this.updatedAt = System.currentTimeMillis();
    }

    public void pruneNonces(long windowMillis) {
        long cutoff = System.currentTimeMillis() - Math.max(windowMillis, 1L);
        processedNonces.entrySet().removeIf(entry -> entry.getValue() < cutoff);
    }

    public boolean hasClaimedOperation(String operationKey) {
        return claimedOperations.containsKey(operationKey);
    }

    public void markClaimedOperation(String operationKey) {
        if (operationKey == null || operationKey.isBlank()) {
            return;
        }
        claimedOperations.put(operationKey, System.currentTimeMillis());
        this.updatedAt = System.currentTimeMillis();
    }

    public void clearClaimedOperation(String operationKey) {
        if (operationKey == null || operationKey.isBlank()) {
            return;
        }
        if (claimedOperations.remove(operationKey) != null) {
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public void pruneClaimedOperations(long retainMillis) {
        long cutoff = System.currentTimeMillis() - Math.max(retainMillis, 1L);
        if (claimedOperations.entrySet().removeIf(entry -> entry.getValue() < cutoff)) {
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public double getTotalGoldEarned() {
        return totalGoldEarned;
    }

    public double getTotalGoldSpent() {
        return totalGoldSpent;
    }

    public long getCreatedAt() {
        return createdAt;
    }

    public long getUpdatedAt() {
        return updatedAt;
    }

    public long getLastJoinAt() {
        return lastJoinAt;
    }

    public void setLastJoinAt(long lastJoinAt) {
        if (this.lastJoinAt != lastJoinAt) {
            this.lastJoinAt = lastJoinAt;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public long getLastQuitAt() {
        return lastQuitAt;
    }

    public void setLastQuitAt(long lastQuitAt) {
        if (this.lastQuitAt != lastQuitAt) {
            this.lastQuitAt = lastQuitAt;
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public List<String> inventorySummary(int limit) {
        List<String> lines = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : inventory.entrySet()) {
            lines.add(entry.getKey() + " x" + entry.getValue());
            if (lines.size() >= limit) {
                break;
            }
        }
        return lines;
    }
}
