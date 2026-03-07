package com.rpg.metrics;

import com.rpg.core.RpgNetworkService;
import java.lang.reflect.Method;
import java.util.Locale;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
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
        register("rpgmetrics");
        getServer().getScheduler().runTaskTimerAsynchronously(this, this::writeMetrics, 40L, 20L * 20L);
        getLogger().info(getDescription().getName() + " enabled");
    }

    private void writeMetrics() {
        double tps = currentTps();
        StringBuilder out = new StringBuilder();
        out.append("rpg_runtime_online_players ").append(Bukkit.getOnlinePlayers().size()).append('\n');
        out.append("rpg_runtime_cached_profiles ").append(service.profileCount()).append('\n');
        out.append("rpg_runtime_dirty_profiles ").append(service.dirtyProfileCount()).append('\n');
        out.append("rpg_runtime_cached_guilds ").append(service.guildCount()).append('\n');
        out.append("rpg_runtime_active_dungeons ").append(service.activeDungeonCount()).append('\n');
        out.append("rpg_runtime_active_instances ").append(service.activeInstanceCount()).append('\n');
        out.append("rpg_runtime_managed_entities ").append(service.managedEntityTotalCount()).append('\n');
        out.append("rpg_runtime_ledger_queue_depth ").append(service.ledgerQueueDepth()).append('\n');
        out.append("rpg_runtime_ledger_pending_files ").append(service.pendingLedgerFileCount()).append('\n');
        out.append("rpg_runtime_db_operations_total ").append(service.dbOperationCount()).append('\n');
        out.append("rpg_runtime_db_operation_errors_total ").append(service.dbOperationErrorCount()).append('\n');
        out.append("rpg_runtime_db_latency_ms_avg ").append(String.format(Locale.US, "%.3f", service.dbLatencyMsAvg())).append('\n');
        out.append("rpg_runtime_db_latency_ms_max ").append(String.format(Locale.US, "%.3f", service.dbLatencyMsMax())).append('\n');
        out.append("rpg_runtime_tps ").append(String.format(Locale.US, "%.2f", tps)).append('\n');
        out.append("rpg_runtime_role{role=\"").append(service.serverRole()).append("\"} 1\n");
        service.writeMetricSnapshot(out.toString());
    }

    private double currentTps() {
        try {
            Method method = Bukkit.getServer().getClass().getMethod("getTPS");
            Object value = method.invoke(Bukkit.getServer());
            if (value instanceof double[] array && array.length > 0) {
                return array[0];
            }
        } catch (ReflectiveOperationException ignored) {
        }
        return 20.0D;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        sender.sendMessage("server=" + service.serverName()
            + " role=" + service.serverRole()
            + " profiles=" + service.profileCount()
            + " dirty=" + service.dirtyProfileCount()
            + " guilds=" + service.guildCount()
            + " activeDungeons=" + service.activeDungeonCount()
            + " activeInstances=" + service.activeInstanceCount()
            + " managedEntities=" + service.managedEntityTotalCount()
            + " ledgerQueue=" + service.ledgerQueueDepth()
            + " pendingLedgerFiles=" + service.pendingLedgerFileCount()
            + " dbAvgMs=" + String.format(Locale.US, "%.3f", service.dbLatencyMsAvg()));
        return true;
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
