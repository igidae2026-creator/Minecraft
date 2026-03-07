package com.rpg.guild;

import com.rpg.core.RpgNetworkService;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;

public class Main extends JavaPlugin implements CommandExecutor {
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
        register("guild");
        getLogger().info(getDescription().getName() + " enabled");
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Players only.");
            return true;
        }
        if (args.length == 0 || args[0].equalsIgnoreCase("info")) {
            sender.sendMessage(service.guildSummary(player));
            return true;
        }
        switch (args[0].toLowerCase()) {
            case "create" -> {
                if (args.length != 2) {
                    sender.sendMessage("/guild create <name>");
                    return true;
                }
                sender.sendMessage(service.createGuild(player, args[1]).message());
                return true;
            }
            case "invite" -> {
                if (args.length != 2) {
                    sender.sendMessage("/guild invite <player>");
                    return true;
                }
                Player target = Bukkit.getPlayerExact(args[1]);
                if (target == null) {
                    sender.sendMessage("Target not online.");
                    return true;
                }
                sender.sendMessage(service.inviteGuild(player, target).message());
                return true;
            }
            case "join" -> {
                if (args.length != 2) {
                    sender.sendMessage("/guild join <name>");
                    return true;
                }
                sender.sendMessage(service.joinGuild(player, args[1]).message());
                return true;
            }
            case "leave" -> {
                sender.sendMessage(service.leaveGuild(player).message());
                return true;
            }
            case "deposit" -> {
                if (args.length < 3) {
                    sender.sendMessage("/guild deposit gold <amount>");
                    sender.sendMessage("/guild deposit item <item> <amount>");
                    return true;
                }
                if (args[1].equalsIgnoreCase("gold")) {
                    double amount;
                    try {
                        amount = Double.parseDouble(args[2]);
                    } catch (NumberFormatException exception) {
                        sender.sendMessage("Invalid amount.");
                        return true;
                    }
                    sender.sendMessage(service.depositGuildGold(player, amount).message());
                    return true;
                }
                if (args[1].equalsIgnoreCase("item") && args.length == 4) {
                    int amount;
                    try {
                        amount = Integer.parseInt(args[3]);
                    } catch (NumberFormatException exception) {
                        sender.sendMessage("Invalid amount.");
                        return true;
                    }
                    sender.sendMessage(service.depositGuildItem(player, args[2], amount).message());
                    return true;
                }
                sender.sendMessage("/guild deposit gold <amount>");
                sender.sendMessage("/guild deposit item <item> <amount>");
                return true;
            }
            default -> {
                sender.sendMessage("/guild info");
                sender.sendMessage("/guild create <name>");
                sender.sendMessage("/guild invite <player>");
                sender.sendMessage("/guild join <name>");
                sender.sendMessage("/guild leave");
                sender.sendMessage("/guild deposit gold <amount>");
                return true;
            }
        }
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
