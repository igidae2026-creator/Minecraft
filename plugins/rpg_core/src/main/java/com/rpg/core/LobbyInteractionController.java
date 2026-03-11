package com.rpg.core;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class LobbyInteractionController {
    public record LobbyRoute(
        String routeId,
        String action,
        String branch,
        String targetServer,
        String destinationLabel,
        String shortDescription,
        String recommendedAction,
        String rewardPreview,
        String icon,
        int slot
    ) {}

    private final Map<String, LobbyRoute> routes = new LinkedHashMap<>();
    private final String menuTitle;
    private final String guideItemName;
    private final String guideDescription;
    private final String openingMessage;

    public LobbyInteractionController(YamlConfiguration config) {
        this.menuTitle = color(config.getString("menu.title", "&6Choose Your Path"));
        this.guideItemName = color(config.getString("menu.guide_item_name", "&6Navigator Compass"));
        this.guideDescription = color(config.getString("menu.guide_item_description", "&7Right-click to open the guided lobby router."));
        this.openingMessage = color(config.getString("menu.opening_message", "&6Welcome. Pick a path to earn your first reward."));
        ConfigurationSection section = config.getConfigurationSection("routes");
        if (section != null) {
            for (String key : section.getKeys(false)) {
                routes.put(key.toLowerCase(Locale.ROOT), new LobbyRoute(
                    key.toLowerCase(Locale.ROOT),
                    normalize(section.getString(key + ".action", "route")),
                    normalize(section.getString(key + ".branch", key)),
                    normalize(section.getString(key + ".target_server", "")),
                    section.getString(key + ".label", key),
                    section.getString(key + ".description", ""),
                    section.getString(key + ".recommended_action", ""),
                    section.getString(key + ".reward_preview", ""),
                    normalize(section.getString(key + ".icon", "compass")),
                    Math.max(0, section.getInt(key + ".slot", routes.size()))
                ));
            }
        }
    }

    public String menuTitle() {
        return menuTitle;
    }

    public String openingMessage() {
        return openingMessage;
    }

    public ItemStack guideItem() {
        ItemStack stack = new ItemStack(Material.COMPASS);
        ItemMeta meta = stack.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(guideItemName);
            meta.setLore(List.of(guideDescription, color("&eUse this any time to pick Adventure, Quick Match, or the rotating Event.")));
            meta.addItemFlags(ItemFlag.HIDE_ATTRIBUTES);
            stack.setItemMeta(meta);
        }
        return stack;
    }

    public Inventory buildInventory() {
        Inventory inventory = Bukkit.createInventory(null, 9, menuTitle);
        List<LobbyRoute> sorted = new ArrayList<>(routes.values());
        sorted.sort(Comparator.comparingInt(LobbyRoute::slot));
        for (LobbyRoute route : sorted) {
            inventory.setItem(route.slot(), routeItem(route));
        }
        return inventory;
    }

    public LobbyRoute routeBySlot(int slot) {
        for (LobbyRoute route : routes.values()) {
            if (route.slot() == slot) {
                return route;
            }
        }
        return null;
    }

    public LobbyRoute routeById(String routeId) {
        return routeId == null ? null : routes.get(routeId.toLowerCase(Locale.ROOT));
    }

    public List<LobbyRoute> routes() {
        return new ArrayList<>(routes.values());
    }

    private ItemStack routeItem(LobbyRoute route) {
        Material material = Material.matchMaterial(route.icon().toUpperCase(Locale.ROOT));
        if (material == null) {
            material = Material.COMPASS;
        }
        ItemStack stack = new ItemStack(material);
        ItemMeta meta = stack.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(color("&e" + route.destinationLabel()));
            List<String> lore = new ArrayList<>();
            lore.add(color("&7" + route.shortDescription()));
            lore.add(color("&fRecommended: &a" + route.recommendedAction()));
            lore.add(color("&fReward Preview: &6" + route.rewardPreview()));
            lore.add(color("&8Route: " + route.routeId()));
            meta.setLore(lore);
            meta.addItemFlags(ItemFlag.HIDE_ATTRIBUTES);
            stack.setItemMeta(meta);
        }
        return stack;
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }

    private String color(String raw) {
        return raw == null ? "" : raw.replace("&", "§");
    }
}
