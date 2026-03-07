package com.rpg.boss;

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
        register("boss");
        getLogger().info(getDescription().getName() + " enabled");
    }

    @EventHandler(ignoreCancelled = true)
    public void onDeath(EntityDeathEvent event) {
        if (!(event.getEntity().getKiller() instanceof Player killer)) {
            return;
        }
        RpgNetworkService.BossReward reward = service.handleBossKill(killer, event.getEntity());
        if (!reward.handled()) {
            return;
        }
        event.getDrops().clear();
        event.setDroppedExp(0);
        killer.sendMessage(reward.message());
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Players only.");
            return true;
        }
        if (args.length < 2 || !args[0].equalsIgnoreCase("summon")) {
            sender.sendMessage("/boss summon <boss_id> [guild]");
            return true;
        }
        boolean guildBank = args.length >= 3 && args[2].equalsIgnoreCase("guild");
        sender.sendMessage(service.summonBoss(player, args[1], guildBank).message());
        return true;
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
