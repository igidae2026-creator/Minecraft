package com.rpg.dungeon;

import com.rpg.core.RpgNetworkService;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;

public class Main extends JavaPlugin implements Listener, CommandExecutor {
    private RpgNetworkService service;

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
        register("dungeon");
        getLogger().info(getDescription().getName() + " enabled");
    }

    @EventHandler(ignoreCancelled = true)
    public void onDeath(EntityDeathEvent event) {
        if (!(event.getEntity().getKiller() instanceof Player killer)) {
            return;
        }
        RpgNetworkService.DungeonProgress progress = service.handleDungeonMobKill(killer, event.getEntity());
        if (progress.handled() && !progress.message().isBlank()) {
            killer.sendMessage(progress.message());
        }
        RpgNetworkService.DungeonCompletion completion = service.handleDungeonBossKill(killer, event.getEntity());
        if (completion.handled() && completion.completed()) {
            killer.sendMessage(completion.message());
        }
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Players only.");
            return true;
        }
        if (args.length == 0 || args[0].equalsIgnoreCase("status")) {
            sender.sendMessage(service.dungeonStatus(player));
            return true;
        }
        if (args[0].equalsIgnoreCase("enter") && args.length == 2) {
            sender.sendMessage(service.startDungeon(player, args[1]).message());
            return true;
        }
        if (args[0].equalsIgnoreCase("abandon")) {
            sender.sendMessage(service.abandonDungeon(player).message());
            return true;
        }
        sender.sendMessage("/dungeon status");
        sender.sendMessage("/dungeon enter <id>");
        sender.sendMessage("/dungeon abandon");
        return true;
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
