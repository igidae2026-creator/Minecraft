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
    private volatile long lastAlertAt;

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
        out.append("rpg_runtime_entity_pressure ").append(String.format(Locale.US, "%.4f", service.entityPressure())).append('\n');
        out.append("rpg_runtime_entity_spawn_denied_total ").append(service.managedEntitySpawnDeniedCount()).append('\n');
        out.append("rpg_runtime_ledger_queue_depth ").append(service.ledgerQueueDepth()).append('\n');
        out.append("rpg_runtime_ledger_pending_files ").append(service.pendingLedgerFileCount()).append('\n');
        out.append("rpg_runtime_db_operations_total ").append(service.dbOperationCount()).append('\n');
        out.append("rpg_runtime_db_operation_errors_total ").append(service.dbOperationErrorCount()).append('\n');
        out.append("rpg_runtime_db_latency_ms_avg ").append(String.format(Locale.US, "%.3f", service.dbLatencyMsAvg())).append('\n');
        out.append("rpg_runtime_db_latency_ms_max ").append(String.format(Locale.US, "%.3f", service.dbLatencyMsMax())).append('\n');
        out.append("rpg_runtime_transfer_fence_rejects_total ").append(service.transferBarrierRejectCount()).append('\n');
        out.append("rpg_runtime_cas_conflicts_total ").append(service.casConflictCount()).append('\n');
        out.append("rpg_runtime_reward_duplicate_suppressed_total ").append(service.rewardDuplicateSuppressionCount()).append('\n');
        out.append("rpg_runtime_duplicate_login_rejects_total ").append(service.duplicateLoginRejectCount()).append('\n');
        out.append("rpg_runtime_transfer_lease_expiry_total ").append(service.transferLeaseExpiryCount()).append('\n');
        out.append("rpg_runtime_startup_quarantine_total ").append(service.startupQuarantineCount()).append('\n');
        out.append("rpg_runtime_reconciliation_mismatches_total ").append(service.reconciliationMismatchCount()).append('\n');
        out.append("rpg_runtime_guild_value_drift_total ").append(service.guildValueDriftCount()).append('\n');
        out.append("rpg_runtime_replay_divergence_total ").append(service.replayDivergenceCount()).append('\n');
        out.append("rpg_runtime_tps ").append(String.format(Locale.US, "%.2f", tps)).append('\n');
        out.append("rpg_runtime_role{role=\"").append(service.serverRole()).append("\"} 1\n");
        service.writeMetricSnapshot(out.toString());
        emitAlerts(tps);
    }

    private void emitAlerts(double tps) {
        long now = System.currentTimeMillis();
        long cooldownMs = Math.max(15_000L, service.scaling().getLong("operational.alert_cooldown_seconds", 30L) * 1000L);
        if (now - lastAlertAt < cooldownMs) {
            return;
        }

        double tpsWarn = Math.max(5.0D, service.scaling().getDouble("operational.alert_tps_below", 17.0D));
        int ledgerWarn = Math.max(1, service.scaling().getInt("operational.alert_ledger_backlog", 64));
        int leakWarn = Math.max(1, service.scaling().getInt("operational.alert_instance_leak", 50));
        int transferFenceWarn = Math.max(1, service.scaling().getInt("operational.alert_transfer_fence_rejects", 5));
        int casConflictWarn = Math.max(1, service.scaling().getInt("operational.alert_cas_conflicts", 5));
        int duplicateLoginWarn = Math.max(1, service.scaling().getInt("operational.alert_duplicate_login_rejects", 2));
        int transferLeaseWarn = Math.max(1, service.scaling().getInt("operational.alert_transfer_lease_expiry", 3));
        int startupQuarantineWarn = Math.max(1, service.scaling().getInt("operational.alert_startup_quarantine", 1));

        if (tps < tpsWarn) {
            getLogger().warning("ALERT tps_drop tps=" + String.format(Locale.US, "%.2f", tps) + " threshold=" + String.format(Locale.US, "%.2f", tpsWarn));
            lastAlertAt = now;
            return;
        }
        if (service.ledgerQueueDepth() >= ledgerWarn || service.pendingLedgerFileCount() >= ledgerWarn) {
            getLogger().warning("ALERT ledger_backlog queue=" + service.ledgerQueueDepth() + " pendingFiles=" + service.pendingLedgerFileCount() + " threshold=" + ledgerWarn);
            lastAlertAt = now;
            return;
        }
        if (service.activeInstanceCount() >= leakWarn) {
            getLogger().warning("ALERT instance_leak activeInstances=" + service.activeInstanceCount() + " threshold=" + leakWarn);
            lastAlertAt = now;
            return;
        }
        if (service.transferBarrierRejectCount() >= transferFenceWarn) {
            getLogger().warning("ALERT transfer_fence_rejects rejects=" + service.transferBarrierRejectCount() + " threshold=" + transferFenceWarn);
            lastAlertAt = now;
            return;
        }
        if (service.casConflictCount() >= casConflictWarn) {
            getLogger().warning("ALERT cas_conflicts count=" + service.casConflictCount() + " threshold=" + casConflictWarn);
            lastAlertAt = now;
            return;
        }
        if (service.duplicateLoginRejectCount() >= duplicateLoginWarn) {
            getLogger().warning("ALERT duplicate_login_rejects count=" + service.duplicateLoginRejectCount() + " threshold=" + duplicateLoginWarn);
            lastAlertAt = now;
            return;
        }
        if (service.transferLeaseExpiryCount() >= transferLeaseWarn) {
            getLogger().warning("ALERT transfer_lease_expiry count=" + service.transferLeaseExpiryCount() + " threshold=" + transferLeaseWarn);
            lastAlertAt = now;
            return;
        }
        if (service.startupQuarantineCount() >= startupQuarantineWarn) {
            getLogger().warning("ALERT startup_quarantine count=" + service.startupQuarantineCount() + " threshold=" + startupQuarantineWarn);
            lastAlertAt = now;
        }
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
            + " entityPressure=" + String.format(Locale.US, "%.4f", service.entityPressure())
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
