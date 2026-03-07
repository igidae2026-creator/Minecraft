package com.rpg.core;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.plugin.java.JavaPlugin;

public class Main extends JavaPlugin implements Listener, CommandExecutor {
    private RpgNetworkService service;

    @Override
    public void onEnable() {
        this.service = new RpgNetworkService(this);
        this.service.enable();
        getServer().getPluginManager().registerEvents(this, this);
        register("rpgprofile");
        register("rpgtravel");
        register("rpgadmin");
        getLogger().info(getDescription().getName() + " enabled on " + service.serverName() + " role=" + service.serverRole());
    }

    @Override
    public void onDisable() {
        if (service != null) {
            service.disable();
        }
        getLogger().info(getDescription().getName() + " disabled");
    }

    public RpgNetworkService service() {
        return service;
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        service.handleJoin(event.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        service.handleQuit(event.getPlayer());
    }


    @EventHandler(ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent event) {
        Location target = event.getTo();
        if (target == null || service.canAccessWorld(event.getPlayer(), target)) {
            return;
        }
        event.setCancelled(true);
        event.getPlayer().sendMessage("§cThis dungeon instance is reserved for another player.");
    }

    @EventHandler
    public void onChangedWorld(PlayerChangedWorldEvent event) {
        service.enforceWorldAccess(event.getPlayer());
    }

    @EventHandler(ignoreCancelled = true)
    public void onCommandPreprocess(PlayerCommandPreprocessEvent event) {
        String input = event.getMessage();
        if (input == null || input.length() <= 1) {
            return;
        }
        String label = input.substring(1).split(" ", 2)[0].toLowerCase();
        if (service.blockedCommands().contains(label) && !event.getPlayer().hasPermission("rpg.admin")) {
            event.setCancelled(true);
            event.getPlayer().sendMessage("§cThat command is blocked on production backends.");
        }
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        switch (command.getName().toLowerCase()) {
            case "rpgprofile" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                player.sendMessage(service.profileSummary(player));
                return true;
            }
            case "rpgtravel" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length != 1) {
                    sender.sendMessage("/rpgtravel <server>");
                    return true;
                }
                RpgNetworkService.OperationResult result = service.travel(player, args[0]);
                sender.sendMessage(result.message());
                return true;
            }
            case "rpgadmin" -> {
                if (!sender.hasPermission("rpg.admin")) {
                    sender.sendMessage("No permission.");
                    return true;
                }
                if (args.length < 1) {
                    sender.sendMessage("/rpgadmin <item|gold|status> ...");
                    return true;
                }
                if (args[0].equalsIgnoreCase("status")) {
                    sender.sendMessage("server=" + service.serverName() + " role=" + service.serverRole() + " cachedProfiles=" + service.profileCount() + " dirtyProfiles=" + service.dirtyProfileCount());
                    return true;
                }
                if (args[0].equalsIgnoreCase("item") && args.length < 4) {
                    sender.sendMessage("/rpgadmin item <player> <item> <amount>");
                    return true;
                }
                if (args[0].equalsIgnoreCase("gold") && args.length < 3) {
                    sender.sendMessage("/rpgadmin gold <player> <delta>");
                    return true;
                }
                if (args.length < 2) {
                    sender.sendMessage("/rpgadmin item <player> <item> <amount>");
                    sender.sendMessage("/rpgadmin gold <player> <delta>");
                    return true;
                }
                Player target = Bukkit.getPlayerExact(args[1]);
                if (target == null) {
                    sender.sendMessage("Target not online.");
                    return true;
                }
                if (args[0].equalsIgnoreCase("item")) {
                    int amount;
                    try {
                        amount = Integer.parseInt(args[3]);
                    } catch (NumberFormatException exception) {
                        sender.sendMessage("Invalid amount.");
                        return true;
                    }
                    sender.sendMessage(service.adminGrantItem(sender, target, args[2], amount).message());
                    return true;
                }
                if (args[0].equalsIgnoreCase("gold")) {
                    double delta;
                    try {
                        delta = Double.parseDouble(args[2]);
                    } catch (NumberFormatException exception) {
                        sender.sendMessage("Invalid delta.");
                        return true;
                    }
                    sender.sendMessage(service.adminAdjustGold(sender, target, delta).message());
                    return true;
                }
                sender.sendMessage("Unknown subcommand.");
                return true;
            }
            default -> {
                return false;
            }
        }
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
