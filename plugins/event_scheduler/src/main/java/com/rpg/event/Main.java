package com.rpg.event;

import com.rpg.core.RpgNetworkService;
import com.rpg.core.RpgProfile;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;

public class Main extends JavaPlugin implements Listener, CommandExecutor {
    private RpgNetworkService service;
    private String activeEventId = "";
    private long activeUntilMillis;
    private long nextRotationAtMillis;

    @Override
    public void onEnable() {
        Plugin plugin = getServer().getPluginManager().getPlugin("rpg_core");
        if (!(plugin instanceof com.rpg.core.Main core) || core.service() == null) {
            getLogger().severe("rpg_core service unavailable");
            getServer().getPluginManager().disablePlugin(this);
            return;
        }
        this.service = core.service();
        getServer().getPluginManager().registerEvents(this, this);
        register("rpgevent");
        loadState();
        if (service.events().contains("events") && service.serverRole().equalsIgnoreCase("event")) {
            long rotationTicks = Math.max(60L, service.events().getLong("rotation_minutes", 30L) * 60L * 20L);
            getServer().getScheduler().runTaskTimer(this, this::tickEvents, 40L, rotationTicks);
        }
        getLogger().info(getDescription().getName() + " enabled");
    }

    @Override
    public void onDisable() {
        if (service == null) {
            return;
        }
        if (!activeEventId.isBlank()) {
            service.cleanupEventEntities(activeEventId);
        }
        saveState();
    }

    @EventHandler(ignoreCancelled = true)
    public void onDeath(EntityDeathEvent event) {
        if (!(event.getEntity().getKiller() instanceof Player killer)) {
            return;
        }
        if (activeEventId.isBlank()) {
            return;
        }
        boolean tagged = event.getEntity().getScoreboardTags().stream().anyMatch(tag -> tag.equals("rpg_event:" + activeEventId));
        if (!tagged) {
            return;
        }
        String expectedMob = service.events().getString("events." + activeEventId + ".mob", "");
        String resolvedMob = service.resolveMobId(event.getEntity());
        if (!expectedMob.equals(resolvedMob)) {
            return;
        }
        if (!service.canClaimReservedEntityKill(killer, event.getEntity())) {
            killer.sendMessage("§cThis event mob is reserved for another player.");
            return;
        }
        event.getDrops().clear();
        event.setDroppedExp(0);
        service.withProfile(killer, profile -> {
            double gold = service.events().getDouble("events." + activeEventId + ".bonus_gold", 0.0D);
            profile.addGold(gold);
            String itemId = service.events().getString("events." + activeEventId + ".bonus_item", "");
            int amount = service.events().getInt("events." + activeEventId + ".bonus_item_amount", 1);
            double chance = service.events().getDouble("events." + activeEventId + ".bonus_item_chance", 0.0D);
            if (!itemId.isBlank() && ThreadLocalRandom.current().nextDouble() < chance) {
                profile.addItem(itemId, amount);
            }
            service.awardSkillXp(profile, "combat", "mob_kill");
            service.syncCollectQuestProgress(profile);
            return null;
        });
        killer.sendMessage("§dEvent bonus: " + activeEventId);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0 || args[0].equalsIgnoreCase("status")) {
            sender.sendMessage(activeEventId.isBlank() ? "No active event." : "active=" + activeEventId + " until=" + activeUntilMillis);
            return true;
        }
        if (!sender.hasPermission("rpg.admin")) {
            sender.sendMessage("No permission.");
            return true;
        }
        if (args[0].equalsIgnoreCase("force") && args.length == 2) {
            if (!service.events().contains("events." + args[1])) {
                sender.sendMessage("Unknown event.");
                return true;
            }
            startEvent(args[1]);
            sender.sendMessage("Forced event " + args[1]);
            return true;
        }
        sender.sendMessage("/rpgevent status");
        sender.sendMessage("/rpgevent force <id>");
        return true;
    }

    private void tickEvents() {
        long now = System.currentTimeMillis();
        if (!activeEventId.isBlank() && now >= activeUntilMillis) {
            String expiredEventId = activeEventId;
            activeEventId = "";
            activeUntilMillis = 0L;
            service.cleanupEventEntities(expiredEventId);
            saveState();
        }
        if (service.isSafeMode()) {
            return;
        }
        if (!activeEventId.isBlank()) {
            return;
        }
        if (now < nextRotationAtMillis) {
            return;
        }
        List<String> ids = new ArrayList<>();
        if (service.events().getConfigurationSection("events") != null) {
            ids.addAll(service.events().getConfigurationSection("events").getKeys(false));
        }
        if (ids.isEmpty()) {
            return;
        }
        startEvent(ids.get(ThreadLocalRandom.current().nextInt(ids.size())));
    }

    private void startEvent(String eventId) {
        if (!service.serverRole().equalsIgnoreCase("event") || service.isSafeMode()) {
            return;
        }
        if (!activeEventId.isBlank()) {
            service.cleanupEventEntities(activeEventId);
        }
        this.activeEventId = eventId;
        this.activeUntilMillis = System.currentTimeMillis() + service.events().getLong("duration_minutes", 10L) * 60_000L;
        this.nextRotationAtMillis = System.currentTimeMillis() + service.events().getLong("rotation_minutes", 30L) * 60_000L;
        saveState();
        String message = service.events().getString("events." + eventId + ".broadcast", eventId + " started");
        Bukkit.broadcastMessage("§d[Event] §f" + message);
        spawnWave(eventId);
        service.writeAudit("event_start", eventId);
    }

    private void spawnWave(String eventId) {
        String mobId = service.events().getString("events." + eventId + ".mob", "");
        int spawnCount = service.events().getInt("events." + eventId + ".spawn_count", 8);
        double radius = service.events().getDouble("events." + eventId + ".spawn_radius", 16.0D);
        for (Player player : Bukkit.getOnlinePlayers()) {
            for (int i = 0; i < spawnCount; i++) {
                Location base = player.getLocation().clone().add(ThreadLocalRandom.current().nextDouble(-radius, radius), 0.0D, ThreadLocalRandom.current().nextDouble(-radius, radius));
                service.spawnConfiguredMob(base, player, mobId, null, eventId);
            }
        }
    }

    private void loadState() {
        try {
            Path path = service.runtimeDir().resolve("events").resolve(service.serverName() + ".yml");
            YamlConfiguration yaml = new YamlConfiguration();
            if (java.nio.file.Files.exists(path)) {
                yaml.loadFromString(java.nio.file.Files.readString(path));
                activeEventId = yaml.getString("active", "");
                activeUntilMillis = yaml.getLong("active_until", 0L);
                nextRotationAtMillis = yaml.getLong("next_rotation_at", 0L);
            }
        } catch (Exception exception) {
            getLogger().warning("Unable to load event state: " + exception.getMessage());
        }
    }

    private void saveState() {
        try {
            Path path = service.runtimeDir().resolve("events").resolve(service.serverName() + ".yml");
            YamlConfiguration yaml = new YamlConfiguration();
            yaml.set("active", activeEventId);
            yaml.set("active_until", activeUntilMillis);
            yaml.set("next_rotation_at", nextRotationAtMillis);
            java.nio.file.Files.createDirectories(path.getParent());
            java.nio.file.Files.writeString(path, yaml.saveToString());
        } catch (Exception exception) {
            getLogger().warning("Unable to save event state: " + exception.getMessage());
        }
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
