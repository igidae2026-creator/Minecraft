package com.rpg.quest;

import com.rpg.core.RpgNetworkService;
import java.util.List;
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
        register("quest");
        getLogger().info(getDescription().getName() + " enabled");
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Players only.");
            return true;
        }
        if (args.length == 0 || args[0].equalsIgnoreCase("list")) {
            List<String> lines = service.questOverview(player);
            lines.forEach(sender::sendMessage);
            return true;
        }
        if (args[0].equalsIgnoreCase("accept") && args.length == 2) {
            sender.sendMessage(service.acceptQuest(player, args[1]).message());
            return true;
        }
        if ((args[0].equalsIgnoreCase("turnin") || args[0].equalsIgnoreCase("complete")) && args.length == 2) {
            sender.sendMessage(service.turnInQuest(player, args[1]).message());
            return true;
        }
        sender.sendMessage("/quest list");
        sender.sendMessage("/quest accept <id>");
        sender.sendMessage("/quest turnin <id>");
        return true;
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
