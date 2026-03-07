package com.rpg.skill;

import com.rpg.core.RpgNetworkService;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
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
        register("skill");
        getLogger().info(getDescription().getName() + " enabled");
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        service.applyPassiveStats(event.getPlayer());
    }

    @EventHandler
    public void onRespawn(PlayerRespawnEvent event) {
        getServer().getScheduler().runTask(this, () -> service.applyPassiveStats(event.getPlayer()));
    }

    @EventHandler(ignoreCancelled = true)
    public void onDamageByEntity(EntityDamageByEntityEvent event) {
        Player player = null;
        if (event.getDamager() instanceof Player direct) {
            player = direct;
        } else if (event.getDamager() instanceof Projectile projectile && projectile.getShooter() instanceof Player shooter) {
            player = shooter;
        }
        if (player != null) {
            service.applyOutgoingDamage(player, event);
        }
        if (event.getEntity() instanceof Player victim) {
            service.applyIncomingDamage(victim, event);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onGenericDamage(EntityDamageEvent event) {
        if (event instanceof EntityDamageByEntityEvent) {
            return;
        }
        Entity entity = event.getEntity();
        if (entity instanceof Player victim) {
            service.applyIncomingDamage(victim, event);
        }
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Players only.");
            return true;
        }
        sender.sendMessage(service.skillSummary(player));
        return true;
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
