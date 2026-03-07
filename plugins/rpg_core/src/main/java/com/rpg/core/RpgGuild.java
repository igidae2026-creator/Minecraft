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
    private double bankGold;
    private final Map<String, Integer> bankItems = new LinkedHashMap<>();
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
        return guild;
    }

    public RpgGuild copy() {
        RpgGuild copy = new RpgGuild(name, ownerUuid);
        copy.members.clear();
        copy.members.addAll(members);
        copy.invites.putAll(invites);
        copy.bankGold = bankGold;
        copy.bankItems.putAll(bankItems);
        copy.createdAt = createdAt;
        copy.updatedAt = updatedAt;
        return copy;
    }

    public YamlConfiguration toYaml() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("name", name);
        yaml.set("owner_uuid", ownerUuid);
        yaml.set("members", new ArrayList<>(members));
        yaml.set("invites", new LinkedHashMap<>(invites));
        yaml.set("bank.gold", bankGold);
        yaml.set("bank.items", new LinkedHashMap<>(bankItems));
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
        this.updatedAt = System.currentTimeMillis();
    }

    public void removeMember(String uuid) {
        members.remove(uuid);
        invites.remove(uuid);
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

    public List<String> bankSummary(int limit) {
        List<String> lines = new ArrayList<>();
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
