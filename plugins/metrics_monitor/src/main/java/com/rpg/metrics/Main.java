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
        out.append("rpg_runtime_composite_pressure ").append(String.format(Locale.US, "%.4f", service.runtimeCompositePressure())).append('\n');
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
        out.append("rpg_runtime_session_ownership_conflicts_total ").append(service.authoritySessionConflictCount()).append('\n');
        out.append("rpg_runtime_split_brain_detections_total ").append(service.authoritySplitBrainDetectionCount()).append('\n');
        out.append("rpg_runtime_item_quarantined_total ").append(service.economyItemQuarantineCount()).append('\n');
        out.append("rpg_runtime_item_ownership_conflicts_total ").append(service.itemOwnershipConflictCount()).append('\n');
        out.append("rpg_runtime_exploit_incidents_total ").append(service.exploitIncidentCount()).append('\n');
        out.append("rpg_runtime_policy_rollbacks_total ").append(service.policyRollbackCount()).append('\n');
        out.append("rpg_runtime_experiment_rollbacks_total ").append(service.experimentRollbackCount()).append('\n');
        out.append("rpg_runtime_transfer_quarantines_total ").append(service.transferQuarantineCount()).append('\n');
        out.append("rpg_runtime_knowledge_records ").append(service.runtimeKnowledgeRecordCount()).append('\n');
        out.append("rpg_runtime_onboarding_started_total ").append(service.onboardingStartedCount()).append('\n');
        out.append("rpg_runtime_onboarding_completed_total ").append(service.onboardingCompletedCount()).append('\n');
        out.append("rpg_runtime_first_interaction_total ").append(service.firstInteractionCount()).append('\n');
        out.append("rpg_runtime_first_reward_granted_total ").append(service.firstRewardGrantedCount()).append('\n');
        out.append("rpg_runtime_first_branch_selected_total ").append(service.firstBranchSelectedCount()).append('\n');
        out.append("rpg_runtime_time_to_first_interaction_seconds_avg ").append(String.format(Locale.US, "%.3f", service.onboardingTimeToFirstInteractionSecondsAvg())).append('\n');
        out.append("rpg_runtime_time_to_first_reward_seconds_avg ").append(String.format(Locale.US, "%.3f", service.onboardingTimeToFirstRewardSecondsAvg())).append('\n');
        out.append("rpg_runtime_genre_entered_total ").append(service.genreEnteredCount()).append('\n');
        out.append("rpg_runtime_genre_exit_total ").append(service.genreExitCount()).append('\n');
        out.append("rpg_runtime_genre_transfer_success_total ").append(service.genreTransferSuccessCount()).append('\n');
        out.append("rpg_runtime_genre_transfer_failure_total ").append(service.genreTransferFailureCount()).append('\n');
        out.append("rpg_runtime_genre_session_duration_seconds_avg ").append(String.format(Locale.US, "%.3f", service.genreSessionDurationSecondsAvg())).append('\n');
        out.append("rpg_runtime_dungeon_started_total ").append(service.dungeonStartedCount()).append('\n');
        out.append("rpg_runtime_dungeon_completed_total ").append(service.dungeonCompletedCount()).append('\n');
        out.append("rpg_runtime_boss_killed_total ").append(service.bossKilledCount()).append('\n');
        out.append("rpg_runtime_event_started_total ").append(service.eventStartedCount()).append('\n');
        out.append("rpg_runtime_event_join_count_total ").append(service.eventJoinCount()).append('\n');
        out.append("rpg_runtime_reward_distributed_total ").append(service.rewardDistributedCount()).append('\n');
        out.append("rpg_runtime_economy_earn_total ").append(service.economyEarnCount()).append('\n');
        out.append("rpg_runtime_economy_spend_total ").append(service.economySpendCount()).append('\n');
        out.append("rpg_runtime_gear_drop_total ").append(service.gearDropCount()).append('\n');
        out.append("rpg_runtime_gear_upgrade_total ").append(service.gearUpgradeMetricCount()).append('\n');
        out.append("rpg_runtime_progression_level_up_total ").append(service.progressionLevelUpCount()).append('\n');
        out.append("rpg_runtime_guild_created_total ").append(service.guildCreatedCount()).append('\n');
        out.append("rpg_runtime_guild_joined_total ").append(service.guildJoinedCount()).append('\n');
        out.append("rpg_runtime_prestige_gain_total ").append(service.prestigeGainCount()).append('\n');
        out.append("rpg_runtime_return_player_reward_total ").append(service.returnPlayerRewardCount()).append('\n');
        out.append("rpg_runtime_streak_progress_total ").append(service.streakProgressCount()).append('\n');
        out.append("rpg_runtime_rivalry_created_total ").append(service.rivalryCreatedCount()).append('\n');
        out.append("rpg_runtime_rivalry_match_total ").append(service.rivalryMatchCount()).append('\n');
        out.append("rpg_runtime_rivalry_reward_total ").append(service.rivalryRewardCount()).append('\n');
        out.append("guild_created ").append(service.guildCreatedCount()).append('\n');
        out.append("guild_joined ").append(service.guildJoinedCount()).append('\n');
        out.append("prestige_gain ").append(service.prestigeGainCount()).append('\n');
        out.append("return_player_reward ").append(service.returnPlayerRewardCount()).append('\n');
        out.append("streak_progress ").append(service.streakProgressCount()).append('\n');
        out.append("runtime_tps ").append(String.format(Locale.US, "%.2f", service.runtimeTps())).append('\n');
        out.append("instance_spawn ").append(service.instanceSpawnCount()).append('\n');
        out.append("instance_shutdown ").append(service.instanceShutdownCount()).append('\n');
        out.append("exploit_flag ").append(service.exploitFlagCount()).append('\n');
        out.append("queue_size ").append(service.queueSize()).append('\n');
        out.append("player_density ").append(service.playerDensity()).append('\n');
        out.append("network_routing_latency_ms ").append(String.format(Locale.US, "%.2f", service.networkRoutingLatencyMs())).append('\n');
        out.append("adaptive_adjustment ").append(service.adaptiveAdjustmentCount()).append('\n');
        out.append("difficulty_change ").append(service.difficultyChangeCount()).append('\n');
        out.append("reward_adjustment ").append(service.rewardAdjustmentCount()).append('\n');
        out.append("event_frequency_change ").append(service.eventFrequencyChangeCount()).append('\n');
        out.append("matchmaking_adjustment ").append(service.matchmakingAdjustmentCount()).append('\n');
        out.append("rpg_runtime_adaptive_adjustment_total ").append(service.adaptiveAdjustmentCount()).append('\n');
        out.append("rpg_runtime_difficulty_change_total ").append(service.difficultyChangeCount()).append('\n');
        out.append("rpg_runtime_reward_adjustment_total ").append(service.rewardAdjustmentCount()).append('\n');
        out.append("rpg_runtime_event_frequency_change_total ").append(service.eventFrequencyChangeCount()).append('\n');
        out.append("rpg_runtime_matchmaking_adjustment_total ").append(service.matchmakingAdjustmentCount()).append('\n');
        out.append("rpg_runtime_instance_cleanup_failures_total ").append(service.cleanupFailureCount()).append('\n');
        out.append("rpg_runtime_instance_cleanup_latency_ms_avg ").append(String.format(Locale.US, "%.3f", service.cleanupLatencyMsAvg())).append('\n');
        out.append("rpg_runtime_instance_cleanup_latency_ms_max ").append(String.format(Locale.US, "%.3f", service.cleanupLatencyMsMax())).append('\n');
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
        int splitBrainWarn = Math.max(1, service.scaling().getInt("operational.alert_split_brain", 1));
        int itemDupWarn = Math.max(1, service.scaling().getInt("operational.alert_item_duplication", 1));
        int guildDriftWarn = Math.max(1, service.scaling().getInt("operational.alert_guild_drift", 1));
        int replayWarn = Math.max(1, service.scaling().getInt("operational.alert_replay_divergence", 1));
        int cleanupWarn = Math.max(1, service.scaling().getInt("operational.alert_instance_cleanup_failure", 1));
        int experimentWarn = Math.max(1, service.scaling().getInt("operational.alert_experiment_anomaly", 1));
        int dbErrorWarn = Math.max(1, service.scaling().getInt("operational.alert_db_saturation", 5));
        int transferQuarantineWarn = Math.max(1, service.scaling().getInt("operational.alert_transfer_ambiguity", 1));

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
        if (service.transferQuarantineCount() >= transferQuarantineWarn) {
            getLogger().warning("ALERT transfer_ambiguity quarantines=" + service.transferQuarantineCount() + " threshold=" + transferQuarantineWarn);
            lastAlertAt = now;
            return;
        }
        if (service.startupQuarantineCount() >= startupQuarantineWarn) {
            getLogger().warning("ALERT startup_quarantine count=" + service.startupQuarantineCount() + " threshold=" + startupQuarantineWarn);
            lastAlertAt = now;
            return;
        }
        if (service.authoritySplitBrainDetectionCount() >= splitBrainWarn) {
            getLogger().warning("ALERT split_brain splitBrain=" + service.authoritySplitBrainDetectionCount() + " threshold=" + splitBrainWarn);
            lastAlertAt = now;
            return;
        }
        if (service.economyItemQuarantineCount() >= itemDupWarn) {
            getLogger().warning("ALERT anti_duplication_alarm quarantined=" + service.economyItemQuarantineCount() + " threshold=" + itemDupWarn);
            lastAlertAt = now;
            return;
        }
        if (service.guildValueDriftCount() >= guildDriftWarn) {
            getLogger().warning("ALERT guild_drift drift=" + service.guildValueDriftCount() + " threshold=" + guildDriftWarn);
            lastAlertAt = now;
            return;
        }
        if (service.replayDivergenceCount() >= replayWarn) {
            getLogger().warning("ALERT replay_divergence divergence=" + service.replayDivergenceCount() + " threshold=" + replayWarn);
            lastAlertAt = now;
            return;
        }
        if (service.cleanupFailureCount() >= cleanupWarn) {
            getLogger().warning("ALERT instance_cleanup_failure failures=" + service.cleanupFailureCount() + " threshold=" + cleanupWarn);
            lastAlertAt = now;
            return;
        }
        if (service.experimentRollbackCount() >= experimentWarn || service.policyRollbackCount() >= experimentWarn) {
            getLogger().warning("ALERT experiment_anomaly experimentRollbacks=" + service.experimentRollbackCount() + " policyRollbacks=" + service.policyRollbackCount() + " threshold=" + experimentWarn);
            lastAlertAt = now;
            return;
        }
        if (service.dbOperationErrorCount() >= dbErrorWarn) {
            getLogger().warning("ALERT db_saturation dbErrors=" + service.dbOperationErrorCount() + " threshold=" + dbErrorWarn);
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
            + " compositePressure=" + String.format(Locale.US, "%.4f", service.runtimeCompositePressure())
            + " ledgerQueue=" + service.ledgerQueueDepth()
            + " pendingLedgerFiles=" + service.pendingLedgerFileCount()
            + " sessionConflicts=" + service.authoritySessionConflictCount()
            + " splitBrain=" + service.authoritySplitBrainDetectionCount()
            + " transferQuarantines=" + service.transferQuarantineCount()
            + " genreTransfers=" + service.genreTransferSuccessCount()
            + "/" + service.genreTransferFailureCount()
            + " dungeonFlow=" + service.dungeonStartedCount()
            + "/" + service.dungeonCompletedCount()
            + " bosses=" + service.bossKilledCount()
            + " events=" + service.eventStartedCount()
            + "/" + service.eventJoinCount()
            + " rewards=" + service.rewardDistributedCount()
            + " economy=" + service.economyEarnCount()
            + "/" + service.economySpendCount()
            + " gear=" + service.gearDropCount()
            + "/" + service.gearUpgradeMetricCount()
            + " progressionUps=" + service.progressionLevelUpCount()
            + " guildSocial=" + service.guildCreatedCount()
            + "/" + service.guildJoinedCount()
            + " prestige=" + service.prestigeGainCount()
            + " returnRewards=" + service.returnPlayerRewardCount()
            + " streaks=" + service.streakProgressCount()
            + " rivalry=" + service.rivalryCreatedCount()
            + "/" + service.rivalryMatchCount()
            + "/" + service.rivalryRewardCount()
            + " queue=" + service.queueSize()
            + " density=" + service.playerDensity()
            + " opsTps=" + String.format(Locale.US, "%.2f", service.runtimeTps())
            + " routeMs=" + String.format(Locale.US, "%.2f", service.networkRoutingLatencyMs())
            + " adaptive=" + service.adaptiveAdjustmentCount()
            + "/" + service.difficultyChangeCount()
            + "/" + service.rewardAdjustmentCount()
            + "/" + service.eventFrequencyChangeCount()
            + "/" + service.matchmakingAdjustmentCount()
            + " guildDrift=" + service.guildValueDriftCount()
            + " itemQuarantine=" + service.economyItemQuarantineCount()
            + " exploitIncidents=" + service.exploitIncidentCount()
            + " experimentAnomalies=" + (service.experimentRollbackCount() + service.policyRollbackCount())
            + " knowledgeRecords=" + service.runtimeKnowledgeRecordCount()
            + " dbAvgMs=" + String.format(Locale.US, "%.3f", service.dbLatencyMsAvg()));
        return true;
    }

    private void register(String command) {
        if (getCommand(command) != null) {
            getCommand(command).setExecutor(this);
        }
    }
}
