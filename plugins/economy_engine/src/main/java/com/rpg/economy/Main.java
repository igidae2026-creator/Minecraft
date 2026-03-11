package com.rpg.economy;

import com.rpg.core.RpgNetworkService;
import java.util.Map;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
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
        register("wallet");
        register("progression");
        register("rpgvendor");
        register("rpgupgrade");
        register("rpgcraft");
        register("rpgrepair");
        register("rpgcosmetic");
        register("rpgbuff");
        getLogger().info(getDescription().getName() + " enabled");
    }

    @EventHandler(ignoreCancelled = true)
    public void onDeath(EntityDeathEvent event) {
        if (!(event.getEntity().getKiller() instanceof Player killer)) {
            return;
        }
        RpgNetworkService.KillReward reward = service.handleMobKill(killer, event.getEntity());
        if (!reward.handled()) {
            return;
        }
        event.getDrops().clear();
        event.setDroppedExp(0);
        killer.sendMessage(reward.message());
    }

    @EventHandler(ignoreCancelled = true)
    public void onDrop(PlayerDropItemEvent event) {
        Item dropped = event.getItemDrop();
        String key = dropped.getItemStack().getType().name().toLowerCase();
        if (service.isTradeRestrictedMaterial(key)) {
            event.setCancelled(true);
            event.getPlayer().sendMessage("Restricted item cannot be dropped or traded across worlds.");
        }
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        switch (command.getName().toLowerCase()) {
            case "wallet" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                sender.sendMessage(service.walletSummary(player));
                return true;
            }
            case "progression" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                sender.sendMessage(service.progressionSummary(player));
                return true;
            }
            case "rpgvendor" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length != 3 || !args[0].equalsIgnoreCase("sell")) {
                    sender.sendMessage("/rpgvendor sell <item> <amount>");
                    return true;
                }
                int amount;
                try {
                    amount = Integer.parseInt(args[2]);
                } catch (NumberFormatException exception) {
                    sender.sendMessage("Invalid amount.");
                    return true;
                }
                sender.sendMessage(service.sellItem(player, args[1], amount).message());
                return true;
            }
            case "rpgupgrade" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length != 1) {
                    sender.sendMessage("/rpgupgrade <gear_path>");
                    return true;
                }
                sender.sendMessage(service.upgradeGear(player, args[0]).message());
                return true;
            }
            case "rpgcraft" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length != 1) {
                    sender.sendMessage("/rpgcraft <recipe>");
                    return true;
                }
                sender.sendMessage(service.craftGear(player, args[0]).message());
                return true;
            }
            case "rpgrepair" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length != 1) {
                    sender.sendMessage("/rpgrepair <gear_path>");
                    return true;
                }
                sender.sendMessage(service.repairGear(player, args[0]).message());
                return true;
            }
            case "rpgcosmetic" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length == 0 || args[0].equalsIgnoreCase("list")) {
                    Map<String, Object> cosmetics = service.economy().getConfigurationSection("economy_model.sinks_runtime.cosmetics") == null
                        ? Map.of() : service.economy().getConfigurationSection("economy_model.sinks_runtime.cosmetics").getValues(false);
                    sender.sendMessage("Cosmetics: " + cosmetics.keySet());
                    return true;
                }
                if (args.length != 2 || (!args[0].equalsIgnoreCase("buy") && !args[0].equalsIgnoreCase("equip"))) {
                    sender.sendMessage("/rpgcosmetic <list|buy|equip> [id]");
                    return true;
                }
                sender.sendMessage(service.unlockCosmetic(player, args[1], args[0].equalsIgnoreCase("equip")).message());
                return true;
            }
            case "rpgbuff" -> {
                if (!(sender instanceof Player player)) {
                    sender.sendMessage("Players only.");
                    return true;
                }
                if (args.length == 0 || args[0].equalsIgnoreCase("list")) {
                    Map<String, Object> buffs = service.economy().getConfigurationSection("economy_model.sinks_runtime.temporary_buffs") == null
                        ? Map.of() : service.economy().getConfigurationSection("economy_model.sinks_runtime.temporary_buffs").getValues(false);
                    sender.sendMessage("Buffs: " + buffs.keySet());
                    return true;
                }
                if (args.length != 2 || !args[0].equalsIgnoreCase("buy")) {
                    sender.sendMessage("/rpgbuff <list|buy> [id]");
                    return true;
                }
                sender.sendMessage(service.buyTemporaryBuff(player, args[1]).message());
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
