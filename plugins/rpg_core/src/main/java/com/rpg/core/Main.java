package com.rpg.core;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerInteractEvent;
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
        register("play");
        register("return");
        register("genres");
        register("party");
        register("prestige");
        register("streak");
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

    @EventHandler
    public void onDeath(PlayerDeathEvent event) {
        service.handlePlayerDeath(event.getEntity());
    }

    @EventHandler(ignoreCancelled = true)
    public void onChat(AsyncPlayerChatEvent event) {
        String message = event.getMessage();
        if (message != null && message.startsWith("@g ")) {
            event.setCancelled(true);
            Bukkit.getScheduler().runTask(this, () -> service.sendGuildChat(event.getPlayer(), message.substring(3)));
        }
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

    @EventHandler(ignoreCancelled = true)
    public void onInteract(PlayerInteractEvent event) {
        if (event.getItem() == null || event.getItem().getType().isAir()) {
            return;
        }
        if (event.getItem().getType().name().equalsIgnoreCase("COMPASS")) {
            service.handleLobbyGuideInteract(event.getPlayer());
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onInventoryClick(InventoryClickEvent event) {
        if (!(event.getWhoClicked() instanceof Player player)) {
            return;
        }
        if (!service.isLobbyMenuTitle(event.getView().getTitle())) {
            return;
        }
        event.setCancelled(true);
        if (event.getCurrentItem() == null || event.getCurrentItem().getType().isAir()) {
            return;
        }
        RpgNetworkService.OperationResult result = service.selectLobbyRoute(player, String.valueOf(event.getSlot()));
        player.sendMessage(result.message());
        if (result.ok()) {
            player.closeInventory();
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
                    sender.sendMessage("/rpgadmin <item|gold|status|ops|forceevent|resetinstance> ...");
                    return true;
                }
                if (args[0].equalsIgnoreCase("status")) {
                    sender.sendMessage("server=" + service.serverName() + " role=" + service.serverRole() + " cachedProfiles=" + service.profileCount() + " dirtyProfiles=" + service.dirtyProfileCount() + " " + service.operationsStatus());
                    return true;
                }
                if (args[0].equalsIgnoreCase("ops")) {
                    if (args.length == 1 || args[1].equalsIgnoreCase("status")) {
                        sender.sendMessage(service.operationsStatus());
                        return true;
                    }
                    if (args.length == 3 && args[1].equalsIgnoreCase("scaling")) {
                        sender.sendMessage(service.setAutoScalingEnabled(args[2].equalsIgnoreCase("on")).message());
                        return true;
                    }
                    if (args.length == 3 && args[1].equalsIgnoreCase("debugmetrics")) {
                        sender.sendMessage(service.setDebugMetricsEnabled(args[2].equalsIgnoreCase("on")).message());
                        return true;
                    }
                    sender.sendMessage("/rpgadmin ops status");
                    sender.sendMessage("/rpgadmin ops scaling <on|off>");
                    sender.sendMessage("/rpgadmin ops debugmetrics <on|off>");
                    return true;
                }
                if (args[0].equalsIgnoreCase("forceevent") && args.length == 2) {
                    sender.sendMessage(service.forceEventStart(args[1]).message());
                    return true;
                }
                if (args[0].equalsIgnoreCase("resetinstance") && args.length == 2) {
                    sender.sendMessage(service.quarantineInstance(args[1], "admin_reset").message());
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
                    sender.sendMessage("/rpgadmin forceevent <id>");
                    sender.sendMessage("/rpgadmin resetinstance <id>");
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
            case "play" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length == 0) {
                    service.openLobbyRouter(player);
                    return true;
                }
                sender.sendMessage(service.selectLobbyRoute(player, args[0]).message());
                return true;
            }
            case "return" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                sender.sendMessage(service.returnToLobby(player).message());
                return true;
            }
            case "genres" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                sender.sendMessage(service.genreMeshSummary(player));
                return true;
            }
            case "party" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length == 0 || args[0].equalsIgnoreCase("info")) {
                    sender.sendMessage(service.partySummary(player));
                    return true;
                }
                if (args[0].equalsIgnoreCase("invite")) {
                    if (args.length < 2) {
                        sender.sendMessage("/party invite <player>");
                        return true;
                    }
                    Player target = Bukkit.getPlayerExact(args[1]);
                    if (target == null) {
                        sender.sendMessage("Target not online.");
                        return true;
                    }
                    sender.sendMessage(service.partyInvite(player, target).message());
                    return true;
                }
                if (args[0].equalsIgnoreCase("accept")) {
                    sender.sendMessage(service.partyAccept(player).message());
                    return true;
                }
                if (args[0].equalsIgnoreCase("leave")) {
                    sender.sendMessage(service.partyLeave(player).message());
                    return true;
                }
                if (args[0].equalsIgnoreCase("warp")) {
                    if (args.length < 2) {
                        sender.sendMessage("/party warp <genre>");
                        return true;
                    }
                    sender.sendMessage(service.partyWarp(player, args[1]).message());
                    return true;
                }
                sender.sendMessage("/party info");
                sender.sendMessage("/party invite <player>");
                sender.sendMessage("/party accept");
                sender.sendMessage("/party leave");
                sender.sendMessage("/party warp <genre>");
                return true;
            }
            case "prestige" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                sender.sendMessage(service.prestigeSummary(player));
                return true;
            }
            case "streak" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                sender.sendMessage(service.streakSummary(player));
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
