package com.rpg.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

public final class RpgGuild {
    private final String name;
    private String ownerUuid;
    private final Set<String> members = new LinkedHashSet<>();
    private final Map<String, Long> invites = new LinkedHashMap<>();
    private final Map<String, String> memberRanks = new LinkedHashMap<>();
    private double bankGold;
    private final Map<String, Integer> bankItems = new LinkedHashMap<>();
    private int guildLevel = 1;
    private int guildPoints;
    private final Map<String, Long> rewardClaims = new LinkedHashMap<>();
    private long createdAt;
    private long updatedAt;

    public RpgGuild(String name, String ownerUuid) {
        this.name = name;
        this.ownerUuid = ownerUuid == null ? "" : ownerUuid;
        long now = System.currentTimeMillis();
        this.createdAt = now;
        this.updatedAt = now;
        if (!this.ownerUuid.isBlank()) {
            this.members.add(this.ownerUuid);
        }
    }

    public static RpgGuild fromYaml(String name, YamlConfiguration yaml) {
        RpgGuild guild = new RpgGuild(name, yaml.getString("owner_uuid", ""));
        guild.members.clear();
        guild.members.addAll(yaml.getStringList("members"));
        guild.ownerUuid = yaml.getString("owner_uuid", guild.members.stream().findFirst().orElse(""));
        guild.bankGold = yaml.getDouble("bank.gold", 0.0D);
        guild.guildLevel = Math.max(1, yaml.getInt("progression.level", 1));
        guild.guildPoints = Math.max(0, yaml.getInt("progression.points", 0));
        guild.createdAt = yaml.getLong("created_at", System.currentTimeMillis());
        guild.updatedAt = yaml.getLong("updated_at", guild.createdAt);

        ConfigurationSection inviteSection = yaml.getConfigurationSection("invites");
        if (inviteSection != null) {
            for (String key : inviteSection.getKeys(false)) {
                guild.invites.put(key, inviteSection.getLong(key, 0L));
            }
        }
        ConfigurationSection itemsSection = yaml.getConfigurationSection("bank.items");
        if (itemsSection != null) {
            for (String key : itemsSection.getKeys(false)) {
                guild.bankItems.put(key.toLowerCase(Locale.ROOT), Math.max(0, itemsSection.getInt(key, 0)));
            }
        }
        ConfigurationSection ranksSection = yaml.getConfigurationSection("members.ranks");
        if (ranksSection != null) {
            for (String key : ranksSection.getKeys(false)) {
                guild.memberRanks.put(key, yaml.getString("members.ranks." + key, "member"));
            }
        }
        ConfigurationSection claimsSection = yaml.getConfigurationSection("progression.reward_claims");
        if (claimsSection != null) {
            for (String key : claimsSection.getKeys(false)) {
                guild.rewardClaims.put(key, claimsSection.getLong(key, 0L));
            }
        }
        guild.memberRanks.putIfAbsent(guild.ownerUuid, "owner");
        for (String member : guild.members) {
            guild.memberRanks.putIfAbsent(member, "member");
        }
        return guild;
    }

    public RpgGuild copy() {
        RpgGuild copy = new RpgGuild(name, ownerUuid);
        copy.members.clear();
        copy.members.addAll(members);
        copy.invites.putAll(invites);
        copy.memberRanks.putAll(memberRanks);
        copy.bankGold = bankGold;
        copy.bankItems.putAll(bankItems);
        copy.guildLevel = guildLevel;
        copy.guildPoints = guildPoints;
        copy.rewardClaims.putAll(rewardClaims);
        copy.createdAt = createdAt;
        copy.updatedAt = updatedAt;
        return copy;
    }

    public YamlConfiguration toYaml() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("name", name);
        yaml.set("owner_uuid", ownerUuid);
        yaml.set("members", new ArrayList<>(members));
        yaml.set("members.ranks", new LinkedHashMap<>(memberRanks));
        yaml.set("invites", new LinkedHashMap<>(invites));
        yaml.set("bank.gold", bankGold);
        yaml.set("bank.items", new LinkedHashMap<>(bankItems));
        yaml.set("progression.level", guildLevel);
        yaml.set("progression.points", guildPoints);
        yaml.set("progression.reward_claims", new LinkedHashMap<>(rewardClaims));
        yaml.set("created_at", createdAt);
        yaml.set("updated_at", updatedAt);
        return yaml;
    }

    public String getName() {
        return name;
    }

    public String getOwnerUuid() {
        return ownerUuid;
    }

    public void setOwnerUuid(String ownerUuid) {
        this.ownerUuid = ownerUuid;
        memberRanks.put(ownerUuid, "owner");
        this.updatedAt = System.currentTimeMillis();
    }

    public Set<String> getMembersView() {
        return Collections.unmodifiableSet(members);
    }

    public boolean isMember(String uuid) {
        return members.contains(uuid);
    }

    public void addMember(String uuid) {
        members.add(uuid);
        invites.remove(uuid);
        memberRanks.putIfAbsent(uuid, "member");
        this.updatedAt = System.currentTimeMillis();
    }

    public void removeMember(String uuid) {
        members.remove(uuid);
        invites.remove(uuid);
        memberRanks.remove(uuid);
        this.updatedAt = System.currentTimeMillis();
    }

    public void invite(String uuid, long expiresAtMillis) {
        invites.put(uuid, expiresAtMillis);
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean hasInvite(String uuid) {
        long expiresAt = invites.getOrDefault(uuid, 0L);
        if (expiresAt <= System.currentTimeMillis()) {
            if (invites.remove(uuid) != null) {
                this.updatedAt = System.currentTimeMillis();
            }
            return false;
        }
        return true;
    }

    public Map<String, Long> getInvitesView() {
        return Collections.unmodifiableMap(invites);
    }

    public void purgeExpiredInvites() {
        long now = System.currentTimeMillis();
        int before = invites.size();
        invites.entrySet().removeIf(entry -> entry.getValue() <= now);
        if (before != invites.size()) {
            this.updatedAt = System.currentTimeMillis();
        }
    }

    public String getRank(String uuid) {
        if (uuid == null || uuid.isBlank()) {
            return "member";
        }
        if (uuid.equals(ownerUuid)) {
            return "owner";
        }
        return memberRanks.getOrDefault(uuid, "member");
    }

    public boolean isOfficer(String uuid) {
        String rank = getRank(uuid);
        return "owner".equalsIgnoreCase(rank) || "officer".equalsIgnoreCase(rank);
    }

    public Map<String, String> getMemberRanksView() {
        return Collections.unmodifiableMap(memberRanks);
    }

    public void setRank(String uuid, String rank) {
        if (uuid == null || uuid.isBlank()) {
            return;
        }
        String next = rank == null || rank.isBlank() ? "member" : rank.toLowerCase(Locale.ROOT);
        if (uuid.equals(ownerUuid)) {
            next = "owner";
        }
        memberRanks.put(uuid, next);
        updatedAt = System.currentTimeMillis();
    }

    public double getBankGold() {
        return bankGold;
    }

    public void addBankGold(double amount) {
        if (amount <= 0.0D) {
            return;
        }
        bankGold += amount;
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean spendBankGold(double amount) {
        if (amount <= 0.0D) {
            return true;
        }
        if (bankGold + 0.000001D < amount) {
            return false;
        }
        bankGold -= amount;
        this.updatedAt = System.currentTimeMillis();
        return true;
    }

    public Map<String, Integer> getBankItemsView() {
        return Collections.unmodifiableMap(bankItems);
    }

    public int getBankItemCount(String itemId) {
        return bankItems.getOrDefault(itemId.toLowerCase(Locale.ROOT), 0);
    }

    public void addBankItem(String itemId, int amount) {
        if (itemId == null || itemId.isBlank() || amount <= 0) {
            return;
        }
        String key = itemId.toLowerCase(Locale.ROOT);
        bankItems.put(key, getBankItemCount(key) + amount);
        this.updatedAt = System.currentTimeMillis();
    }

    public boolean removeBankItem(String itemId, int amount) {
        if (amount <= 0) {
            return true;
        }
        String key = itemId.toLowerCase(Locale.ROOT);
        int current = getBankItemCount(key);
        if (current < amount) {
            return false;
        }
        int next = current - amount;
        if (next <= 0) {
            bankItems.remove(key);
        } else {
            bankItems.put(key, next);
        }
        this.updatedAt = System.currentTimeMillis();
        return true;
    }

    public long getCreatedAt() {
        return createdAt;
    }

    public long getUpdatedAt() {
        return updatedAt;
    }

    public int getGuildLevel() {
        return guildLevel;
    }

    public void setGuildLevel(int guildLevel) {
        int next = Math.max(1, guildLevel);
        if (this.guildLevel != next) {
            this.guildLevel = next;
            updatedAt = System.currentTimeMillis();
        }
    }

    public int getGuildPoints() {
        return guildPoints;
    }

    public void addGuildPoints(int delta) {
        if (delta <= 0) {
            return;
        }
        guildPoints += delta;
        updatedAt = System.currentTimeMillis();
    }

    public boolean hasClaimedReward(String key) {
        return rewardClaims.containsKey(key);
    }

    public void markRewardClaimed(String key) {
        if (key == null || key.isBlank()) {
            return;
        }
        rewardClaims.put(key, System.currentTimeMillis());
        updatedAt = System.currentTimeMillis();
    }

    public Map<String, Long> getRewardClaimsView() {
        return Collections.unmodifiableMap(rewardClaims);
    }

    public List<String> bankSummary(int limit) {
        List<String> lines = new ArrayList<>();
        lines.add("lv=" + guildLevel + " pts=" + guildPoints);
        lines.add("gold=" + String.format(Locale.US, "%.2f", bankGold));
        for (Map.Entry<String, Integer> entry : bankItems.entrySet()) {
            lines.add(entry.getKey() + " x" + entry.getValue());
            if (lines.size() >= limit) {
                break;
            }
        }
        return lines;
    }
}
