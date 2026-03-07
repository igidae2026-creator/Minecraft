package com.rpg.core;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.DateTimeException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;
import java.security.MessageDigest;
import java.util.StringJoiner;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;
import java.util.function.Function;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.WorldType;
import org.bukkit.attribute.Attribute;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

public final class RpgNetworkService {
    private static final long CLAIM_RETENTION_MILLIS = 14L * 24L * 60L * 60L * 1000L;
    private static final ZoneId DEFAULT_REWARD_ZONE = ZoneOffset.UTC;
    public record OperationResult(boolean ok, String message) {}
    public record KillReward(boolean handled, String mobId, double gold, Map<String, Integer> items, String message) {}
    public record BossReward(boolean handled, String bossId, boolean rewarded, double bonusGold, Map<String, Integer> items, String message) {}
    public record DungeonStart(boolean ok, String dungeonId, int spawnedMobs, String message) {}
    public record DungeonProgress(boolean handled, boolean bossSpawned, String message) {}
    public record DungeonCompletion(boolean handled, boolean completed, String dungeonId, double gold, Map<String, Integer> items, String message) {}
    public record BossSummonResult(boolean ok, String bossId, String message, LivingEntity entity) {}
    private record LiveSession(String server, String role, boolean online, String guild, String activeDungeon, String activeDungeonInstanceId, long updatedAt) {}
    private record TravelTicket(String transferId, String transferLease, String sourceServer, String targetServer, long issuedAt, long expiresAt,
                                long expectedProfileVersion, long expectedInventoryVersion, long expectedEconomyVersion,
                                String guildName, long expectedGuildVersion, long versionClaim) {}
    private enum PersistOutcome {
        SUCCESS,
        CONFLICT,
        UNAVAILABLE
    }
    private record LedgerEntry(String operationId, String server, long sequence, long createdAt, UUID playerUuid, String category, String reference, double goldDelta, Map<String, Integer> itemDelta, String payload, String payloadHash) {}
    private record LedgerPayloadSnapshot(String operationId, long sequence, long createdAt, String server, UUID playerUuid, String category,
                                         String reference, double goldDelta, Map<String, Integer> itemDelta, long previousHash, long entryHash, String payloadHash) {}

    private enum InstanceLifecycleState {
        REQUESTED,
        ALLOCATING,
        BOOTING,
        READY,
        ACTIVE,
        RESOLVING,
        REWARD_COMMIT,
        EGRESS,
        CLEANUP,
        TERMINATED
    }

    private enum InstanceType {
        DUNGEON,
        BOSS_ENCOUNTER
    }

    private static final class DungeonInstanceState {
        private final String instanceId;
        private final UUID ownerUuid;
        private final String dungeonId;
        private final String worldName;
        private final long createdAt;
        private final InstanceType type;
        private final Set<UUID> partyMembers = new LinkedHashSet<>();
        private InstanceLifecycleState lifecycleState;
        private long allocationRequestedAt;
        private long allocationCompletedAt;
        private long expiresAt;

        private DungeonInstanceState(String instanceId, UUID ownerUuid, String dungeonId, String worldName, long createdAt, long expiresAt, InstanceType type,
                                     InstanceLifecycleState lifecycleState, long allocationRequestedAt, long allocationCompletedAt, Set<UUID> partyMembers) {
            this.instanceId = instanceId;
            this.ownerUuid = ownerUuid;
            this.dungeonId = dungeonId;
            this.worldName = worldName;
            this.createdAt = createdAt;
            this.expiresAt = expiresAt;
            this.type = type;
            this.lifecycleState = lifecycleState;
            this.allocationRequestedAt = allocationRequestedAt;
            this.allocationCompletedAt = allocationCompletedAt;
            this.partyMembers.addAll(partyMembers);
        }

        private static DungeonInstanceState create(UUID ownerUuid, String dungeonId, long ttlMillis, InstanceType type, Set<UUID> partyMembers) {
            long now = System.currentTimeMillis();
            String compact = ownerUuid.toString().replace("-", "");
            String ownerPart = compact.substring(0, Math.min(8, compact.length()));
            String entropy = Long.toHexString(now) + Integer.toHexString(ThreadLocalRandom.current().nextInt(0x1000, 0x10000));
            String prefix = type == InstanceType.BOSS_ENCOUNTER ? "enc" : dungeonId.toLowerCase(Locale.ROOT);
            String instanceId = prefix + "-" + ownerPart + "-" + entropy;
            String worldName = "inst_" + instanceId;
            return new DungeonInstanceState(
                instanceId,
                ownerUuid,
                dungeonId,
                worldName,
                now,
                now + ttlMillis,
                type,
                InstanceLifecycleState.REQUESTED,
                now,
                0L,
                partyMembers
            );
        }

        private static DungeonInstanceState fromYaml(YamlConfiguration yaml) {
            String instanceId = yaml.getString("instance_id", "");
            String owner = yaml.getString("owner_uuid", "");
            String dungeonId = yaml.getString("dungeon_id", "");
            String worldName = yaml.getString("world", "");
            long createdAt = yaml.getLong("created_at", System.currentTimeMillis());
            long expiresAt = yaml.getLong("expires_at", createdAt);
            String typeRaw = yaml.getString("type", InstanceType.DUNGEON.name());
            String stateRaw = yaml.getString("state", InstanceLifecycleState.REQUESTED.name());
            long requestedAt = yaml.getLong("allocation.requested_at", createdAt);
            long completedAt = yaml.getLong("allocation.completed_at", 0L);
            if (instanceId.isBlank() || owner.isBlank() || dungeonId.isBlank() || worldName.isBlank()) {
                return null;
            }
            InstanceType type;
            InstanceLifecycleState state;
            try {
                type = InstanceType.valueOf(typeRaw.toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException exception) {
                type = InstanceType.DUNGEON;
            }
            try {
                state = InstanceLifecycleState.valueOf(stateRaw.toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException exception) {
                state = InstanceLifecycleState.REQUESTED;
            }
            Set<UUID> members = new LinkedHashSet<>();
            for (String member : yaml.getStringList("party.members")) {
                try {
                    members.add(UUID.fromString(member));
                } catch (IllegalArgumentException ignored) {
                }
            }
            try {
                UUID ownerUuid = UUID.fromString(owner);
                members.add(ownerUuid);
                return new DungeonInstanceState(instanceId, ownerUuid, dungeonId, worldName, createdAt, expiresAt, type, state, requestedAt, completedAt, members);
            } catch (IllegalArgumentException ignored) {
                return null;
            }
        }

        private YamlConfiguration toYaml() {
            YamlConfiguration yaml = new YamlConfiguration();
            yaml.set("instance_id", instanceId);
            yaml.set("owner_uuid", ownerUuid.toString());
            yaml.set("dungeon_id", dungeonId);
            yaml.set("world", worldName);
            yaml.set("created_at", createdAt);
            yaml.set("expires_at", expiresAt);
            yaml.set("type", type.name());
            yaml.set("state", lifecycleState.name());
            yaml.set("allocation.requested_at", allocationRequestedAt);
            yaml.set("allocation.completed_at", allocationCompletedAt);
            List<String> members = new ArrayList<>();
            for (UUID member : partyMembers) {
                members.add(member.toString());
            }
            yaml.set("party.members", members);
            return yaml;
        }

        private boolean expired(long now) {
            return expiresAt > 0L && now >= expiresAt;
        }

        private void extendTo(long nextExpiry) {
            this.expiresAt = Math.max(this.expiresAt, nextExpiry);
        }

        private void setLifecycleState(InstanceLifecycleState state) {
            this.lifecycleState = state;
            if (state == InstanceLifecycleState.ALLOCATING) {
                this.allocationRequestedAt = System.currentTimeMillis();
            }
            if (state == InstanceLifecycleState.READY || state == InstanceLifecycleState.ACTIVE) {
                this.allocationCompletedAt = System.currentTimeMillis();
            }
        }

        private long allocationLatencyMillis() {
            if (allocationCompletedAt <= 0L || allocationRequestedAt <= 0L) {
                return -1L;
            }
            return Math.max(0L, allocationCompletedAt - allocationRequestedAt);
        }

        private boolean isPartyMember(UUID playerUuid) {
            return playerUuid != null && partyMembers.contains(playerUuid);
        }
    }

    private final class InstanceOrchestrator {
        private DungeonInstanceState allocateDungeonInstance(UUID ownerUuid, String dungeonId, Set<UUID> partyMembers) {
            cleanupOwnedDungeonInstance(ownerUuid, "replace");
            DungeonInstanceState instance = DungeonInstanceState.create(ownerUuid, dungeonId, instanceHoldMillis(), InstanceType.DUNGEON, partyMembers);
            instance.setLifecycleState(InstanceLifecycleState.ALLOCATING);
            persistDungeonInstance(instance);
            return instance;
        }

        private DungeonInstanceState allocateBossEncounter(UUID ownerUuid, String bossId, Set<UUID> partyMembers) {
            DungeonInstanceState instance = DungeonInstanceState.create(ownerUuid, "boss_" + bossId, instanceHoldMillis(), InstanceType.BOSS_ENCOUNTER, partyMembers);
            instance.setLifecycleState(InstanceLifecycleState.ALLOCATING);
            persistDungeonInstance(instance);
            return instance;
        }

        private World bootInstanceWorld(DungeonInstanceState instance) {
            if (instance == null) {
                return null;
            }
            instance.setLifecycleState(InstanceLifecycleState.BOOTING);
            persistDungeonInstance(instance);
            World world = instanceOrchestrator.bootInstanceWorld(instance);
            if (world == null) {
                return null;
            }
            instance.setLifecycleState(InstanceLifecycleState.READY);
            persistDungeonInstance(instance);
            long latency = instance.allocationLatencyMillis();
            if (latency >= 0L) {
                allocationLatencyCount.incrementAndGet();
                allocationLatencyTotalMillis.addAndGet(latency);
                allocationLatencyMaxMillis.accumulateAndGet(latency, Math::max);
            }
            return world;
        }

        private void activate(DungeonInstanceState instance) {
            if (instance == null) {
                return;
            }
            instance.setLifecycleState(InstanceLifecycleState.ACTIVE);
            persistDungeonInstance(instance);
        }

        private void resolve(DungeonInstanceState instance) {
            if (instance == null) {
                return;
            }
            instance.setLifecycleState(InstanceLifecycleState.RESOLVING);
            persistDungeonInstance(instance);
        }

        private void rewardCommit(DungeonInstanceState instance) {
            if (instance == null) {
                return;
            }
            instance.setLifecycleState(InstanceLifecycleState.REWARD_COMMIT);
            persistDungeonInstance(instance);
        }

        private void beginEgress(DungeonInstanceState instance) {
            if (instance == null) {
                return;
            }
            instance.setLifecycleState(InstanceLifecycleState.EGRESS);
            persistDungeonInstance(instance);
        }

        private void markCleanup(DungeonInstanceState instance) {
            if (instance == null) {
                return;
            }
            instance.setLifecycleState(InstanceLifecycleState.CLEANUP);
            persistDungeonInstance(instance);
        }

        private void markTerminated(DungeonInstanceState instance) {
            if (instance == null) {
                return;
            }
            instance.setLifecycleState(InstanceLifecycleState.TERMINATED);
            persistDungeonInstance(instance);
        }
    }

    private final JavaPlugin plugin;
    private final Path root;
    private final Path runtimeDir;
    private final Path profileDir;
    private final Path guildDir;
    private final Path sessionDir;
    private final Path ticketDir;
    private final Path instanceDir;
    private final Path auditDir;
    private final Path ledgerDir;
    private final Path ledgerPendingDir;
    private final Path metricsDir;
    private final Path eventDir;
    private final String serverName;
    private final String serverRole;
    private final YamlConfiguration network;
    private final YamlConfiguration persistence;
    private final YamlConfiguration scaling;
    private final YamlConfiguration exploit;
    private final YamlConfiguration economy;
    private final YamlConfiguration items;
    private final YamlConfiguration mobs;
    private final YamlConfiguration quests;
    private final YamlConfiguration bosses;
    private final YamlConfiguration dungeons;
    private final YamlConfiguration skills;
    private final YamlConfiguration events;
    private final Map<UUID, RpgProfile> profiles = new ConcurrentHashMap<>();
    private final Map<String, RpgGuild> guilds = new ConcurrentHashMap<>();
    private final Set<UUID> dirtyProfiles = ConcurrentHashMap.newKeySet();
    private final Set<String> dirtyGuilds = ConcurrentHashMap.newKeySet();
    private final Map<UUID, Object> profileLocks = new ConcurrentHashMap<>();
    private final Map<String, Object> guildLocks = new ConcurrentHashMap<>();
    private final Map<UUID, Long> lastFlushedProfileVersion = new ConcurrentHashMap<>();
    private final Map<String, Long> lastFlushedGuildVersion = new ConcurrentHashMap<>();
    private final Map<UUID, Long> lastMobRewardAt = new ConcurrentHashMap<>();
    private final Map<UUID, Long> lastCommandAt = new ConcurrentHashMap<>();
    private final Set<UUID> transferFrozenProfiles = ConcurrentHashMap.newKeySet();
    private final Map<String, BukkitTask> bossTasks = new ConcurrentHashMap<>();
    private final ConcurrentLinkedQueue<LedgerEntry> ledgerQueue = new ConcurrentLinkedQueue<>();
    private final int ledgerServerId;
    private final AtomicInteger ledgerCounter = new AtomicInteger();
    private volatile long ledgerCounterMillis;
    private final AtomicLong ledgerHashChain = new AtomicLong(0L);
    private final AtomicLong ledgerLastFlushAt = new AtomicLong(0L);
    private final Map<String, DungeonInstanceState> dungeonInstances = new ConcurrentHashMap<>();
    private final Map<UUID, String> dungeonOwnerInstances = new ConcurrentHashMap<>();
    private final Map<String, String> dungeonWorldToInstance = new ConcurrentHashMap<>();
    private final AtomicLong orphanInstancesCleaned = new AtomicLong();
    private final AtomicLong allocationLatencyCount = new AtomicLong();
    private final AtomicLong allocationLatencyTotalMillis = new AtomicLong();
    private final AtomicLong allocationLatencyMaxMillis = new AtomicLong();
    private final InstanceOrchestrator instanceOrchestrator = new InstanceOrchestrator();
    private final Map<String, Integer> managedEntityCounters = new ConcurrentHashMap<>();
    private final Set<UUID> managedEntityIds = ConcurrentHashMap.newKeySet();
    private final AtomicLong dbOperationCount = new AtomicLong();
    private final AtomicLong dbOperationErrors = new AtomicLong();
    private final AtomicLong dbLatencyTotalNanos = new AtomicLong();
    private final AtomicLong dbLatencyMaxNanos = new AtomicLong();
    private final AtomicLong managedEntitySpawnDenied = new AtomicLong();
    private final AtomicLong transferBarrierRejects = new AtomicLong();
    private final AtomicLong casConflictCount = new AtomicLong();
    private final AtomicLong rewardDuplicateSuppressed = new AtomicLong();
    private volatile boolean mysqlSchemaReady;
    private volatile boolean mysqlDriverReady;
    private volatile boolean mysqlDriverUnavailableLogged;
    private volatile boolean safeMode;
    private volatile String safeModeReason = "";
    private volatile long lastEntityPressureWarningAt;
    private HikariDataSource mysqlPool;
    private BukkitTask flushTask;
    private BukkitTask ledgerFlushTask;
    private BukkitTask healthTask;
    private BukkitTask entityCleanupTask;
    private BukkitTask instanceCleanupTask;

    public RpgNetworkService(JavaPlugin plugin) {
        this.plugin = plugin;
        this.root = locateRoot(plugin);
        this.network = loadConfig("network.yml");
        this.persistence = loadConfig("persistence.yml");
        this.scaling = loadConfig("scaling.yml");
        this.exploit = loadConfig("exploit_guards.yml");
        this.economy = loadConfig("economy.yml");
        this.items = loadConfig("items.yml");
        this.mobs = loadConfig("mobs.yml");
        this.quests = loadConfig("quests.yml");
        this.bosses = loadConfig("bosses.yml");
        this.dungeons = loadConfig("dungeons.yml");
        this.skills = loadConfig("skills.yml");
        this.events = loadOptionalConfig("events.yml");
        this.serverName = resolveServerName();
        this.serverRole = resolveServerRole();
        this.ledgerServerId = resolveLedgerServerId(serverName);
        this.ledgerCounterMillis = System.currentTimeMillis();
        String runtimeFolder = persistence.getString("local_fallback.path", "runtime_data");
        this.runtimeDir = root.resolve(runtimeFolder);
        this.profileDir = runtimeDir.resolve("profiles");
        this.guildDir = runtimeDir.resolve("guilds");
        this.sessionDir = runtimeDir.resolve("sessions");
        this.ticketDir = runtimeDir.resolve("travel_tickets");
        this.instanceDir = runtimeDir.resolve("instances");
        this.auditDir = runtimeDir.resolve("audit");
        this.ledgerDir = runtimeDir.resolve("ledger");
        this.ledgerPendingDir = ledgerDir.resolve("pending");
        this.metricsDir = root.resolve("metrics");
        this.eventDir = runtimeDir.resolve("events");
    }

    public void enable() {
        ensurePath(profileDir);
        ensurePath(guildDir);
        ensurePath(sessionDir);
        ensurePath(ticketDir);
        ensurePath(instanceDir);
        ensurePath(auditDir);
        ensurePath(ledgerDir);
        ensurePath(ledgerPendingDir);
        ensurePath(metricsDir);
        ensurePath(eventDir);
        validateBackendBaseline();
        loadPendingLedgerEntries();
        loadPersistedInstances();
        rebuildManagedEntityCounters();
        plugin.getServer().getMessenger().registerOutgoingPluginChannel(plugin, "BungeeCord");
        long flushIntervalTicks = Math.max(20L, persistence.getLong("write_policy.profile_save_interval_seconds", 60L) * 20L);
        long ledgerFlushTicks = Math.max(1L, persistence.getLong("write_policy.ledger_flush_interval_seconds", 1L) * 20L);
        flushTask = Bukkit.getScheduler().runTaskTimerAsynchronously(plugin, this::flushDirty, flushIntervalTicks, flushIntervalTicks);
        ledgerFlushTask = Bukkit.getScheduler().runTaskTimerAsynchronously(plugin, this::flushLedger, ledgerFlushTicks, ledgerFlushTicks);
        healthTask = Bukkit.getScheduler().runTaskTimerAsynchronously(plugin, this::writeHealthSnapshot, 20L, 20L * 30L);
        entityCleanupTask = Bukkit.getScheduler().runTaskTimer(plugin, this::cleanupTaggedEntities, 20L * 15L, 20L * 15L);
        instanceCleanupTask = Bukkit.getScheduler().runTaskTimer(plugin, this::cleanupExpiredInstances, 20L * 10L, 20L * 10L);
        evaluateBackendSafety();
        writeHealthSnapshot();
        plugin.getLogger().info("RPG core service ready for " + serverName + " role=" + serverRole + " root=" + root);
    }

    public void disable() {
        if (flushTask != null) {
            flushTask.cancel();
        }
        if (healthTask != null) {
            healthTask.cancel();
        }
        if (ledgerFlushTask != null) {
            ledgerFlushTask.cancel();
        }
        if (entityCleanupTask != null) {
            entityCleanupTask.cancel();
        }
        if (instanceCleanupTask != null) {
            instanceCleanupTask.cancel();
        }
        for (BukkitTask task : bossTasks.values()) {
            task.cancel();
        }
        bossTasks.clear();
        flushDirty();
        closeMysqlPool();
    }

    public JavaPlugin plugin() {
        return plugin;
    }

    public Path root() {
        return root;
    }

    public Path runtimeDir() {
        return runtimeDir;
    }

    public Path metricsDir() {
        return metricsDir;
    }

    public String serverName() {
        return serverName;
    }

    public String serverRole() {
        return serverRole;
    }

    public boolean isSafeMode() {
        return safeMode;
    }

    public YamlConfiguration network() {
        return network;
    }

    public YamlConfiguration persistence() {
        return persistence;
    }

    public YamlConfiguration scaling() {
        return scaling;
    }

    public YamlConfiguration exploit() {
        return exploit;
    }

    public YamlConfiguration economy() {
        return economy;
    }

    public YamlConfiguration items() {
        return items;
    }

    public YamlConfiguration mobs() {
        return mobs;
    }

    public YamlConfiguration quests() {
        return quests;
    }

    public YamlConfiguration bosses() {
        return bosses;
    }

    public YamlConfiguration dungeons() {
        return dungeons;
    }

    public YamlConfiguration skills() {
        return skills;
    }

    public YamlConfiguration events() {
        return events;
    }

    public int profileCount() {
        return profiles.size();
    }

    public int dirtyProfileCount() {
        return dirtyProfiles.size();
    }

    public int guildCount() {
        return guilds.size();
    }

    public int activeDungeonCount() {
        int total = 0;
        for (RpgProfile profile : profiles.values()) {
            if (!profile.getActiveDungeon().isBlank()) {
                total += 1;
            }
        }
        return total;
    }

    public int activeInstanceCount() {
        return dungeonInstances.size();
    }

    public int orphanInstanceCount() {
        int total = 0;
        for (DungeonInstanceState instance : dungeonInstances.values()) {
            if (Bukkit.getPlayer(instance.ownerUuid) == null) {
                total += 1;
            }
        }
        return total;
    }

    public double allocationLatencyMsAvg() {
        long count = allocationLatencyCount.get();
        if (count <= 0L) {
            return 0.0D;
        }
        return allocationLatencyTotalMillis.get() / (double) count;
    }

    public double allocationLatencyMsMax() {
        return allocationLatencyMaxMillis.get();
    }

    public int managedEntityTotalCount() {
        return managedEntityCount(null);
    }

    public double entityPressure() {
        int serverCap = Math.max(1, scaling.getInt("limits.max_entities_per_server." + serverName, Integer.MAX_VALUE));
        if (serverCap >= Integer.MAX_VALUE / 2) {
            return 0.0D;
        }
        return Math.min(1.0D, managedEntityTotalCount() / (double) serverCap);
    }

    public long managedEntitySpawnDeniedCount() {
        return managedEntitySpawnDenied.get();
    }

    public long transferBarrierRejectCount() {
        return transferBarrierRejects.get();
    }

    public long casConflictCount() {
        return casConflictCount.get();
    }

    public long rewardDuplicateSuppressionCount() {
        return rewardDuplicateSuppressed.get();
    }

    public int ledgerQueueDepth() {
        return ledgerQueue.size();
    }

    public int pendingLedgerFileCount() {
        if (!Files.exists(ledgerPendingDir)) {
            return 0;
        }
        try (var stream = Files.list(ledgerPendingDir)) {
            return (int) stream.filter(path -> path.getFileName().toString().endsWith(".yml")).count();
        } catch (IOException exception) {
            return 0;
        }
    }

    public double dbLatencyMsAvg() {
        long ops = dbOperationCount.get();
        if (ops <= 0) {
            return 0.0D;
        }
        return (dbLatencyTotalNanos.get() / 1_000_000.0D) / ops;
    }

    public double dbLatencyMsMax() {
        return dbLatencyMaxNanos.get() / 1_000_000.0D;
    }

    public long dbOperationCount() {
        return dbOperationCount.get();
    }

    public long dbOperationErrorCount() {
        return dbOperationErrors.get();
    }

    public Set<String> blockedCommands() {
        Set<String> blocked = new LinkedHashSet<>();
        if (exploit.getBoolean("network.reload_commands_blocked", true)) {
            Collections.addAll(blocked,
                "reload", "rl", "minecraft:reload", "bukkit:reload",
                "plugman", "plugmanx", "version", "ver", "plugins", "pl", "bukkit:plugins",
                "server", "send"
            );
        }
        return blocked;
    }

    public void handleJoin(Player player) {
        if (!authorizeJoin(player, loadLiveSession(player.getUniqueId()))) {
            return;
        }
        RpgProfile sessionSnapshot = withProfile(player, profile -> {
            if (profile.getCreatedAt() == profile.getUpdatedAt() && profile.getGold() <= 0.0D) {
                profile.addGold(economy.getDouble("starting_balance", 25.0D));
            }
            ConfigurationSection gearPaths = items.getConfigurationSection("gear_paths");
            if (gearPaths != null) {
                for (String gearPath : gearPaths.getKeys(false)) {
                    profile.ensureGearTier(gearPath, gearPaths.getString(gearPath + ".starting_tier", "common"));
                }
            }
            long reconnectHoldMillis = exploit.getLong("progression.reconnect_state_hold_seconds", 30L) * 1000L;
            if (!profile.getActiveDungeon().isBlank() && profile.getLastQuitAt() > 0L
                && System.currentTimeMillis() - profile.getLastQuitAt() > reconnectHoldMillis) {
                cleanupOwnedDungeonInstance(player.getUniqueId(), "reconnect_timeout");
                profile.clearActiveDungeon();
            }
            profile.setLastJoinAt(System.currentTimeMillis());
            autoAcceptStarterQuest(profile);
            syncCollectQuestProgress(profile);
            restoreDungeonInstance(player, profile);
            return profile.copy();
        });
        writeSession(sessionSnapshot, true);
        applyPassiveStats(player);
        if (safeMode) {
            player.sendMessage(color("&cBackend safe mode active: &e" + safeModeReason));
        }
        player.sendMessage(color("&6RPG &7profile synced. Use &e/rpgprofile&7, &e/quest list&7, &e/wallet&7."));
    }

    public void handleQuit(Player player) {
        RpgProfile sessionSnapshot = withProfile(player, profile -> {
            profile.setLastQuitAt(System.currentTimeMillis());
            holdDungeonInstance(profile);
            return profile.copy();
        });
        writeSession(sessionSnapshot, false);
        flushPlayer(player.getUniqueId());
    }

    public <T> T withProfile(Player player, Function<RpgProfile, T> action) {
        return withProfile(player.getUniqueId(), player.getName(), action);
    }

    public <T> T withProfile(UUID uuid, String latestName, Function<RpgProfile, T> action) {
        Objects.requireNonNull(action, "action");
        synchronized (profileLocks.computeIfAbsent(uuid, ignored -> new Object())) {
            if (isMutationFrozen(uuid)) {
                throw new IllegalStateException("Profile mutation authority is frozen during transfer");
            }
            RpgProfile profile = profiles.computeIfAbsent(uuid, ignored -> loadProfile(uuid, latestName));
            long before = profile.getUpdatedAt();
            profile.touch(latestName);
            T value = action.apply(profile);
            if (profile.getUpdatedAt() != before) {
                dirtyProfiles.add(uuid);
            }
            return value;
        }
    }

    public <T> T withProfileRead(UUID uuid, String latestName, Function<RpgProfile, T> action) {
        Objects.requireNonNull(action, "action");
        synchronized (profileLocks.computeIfAbsent(uuid, ignored -> new Object())) {
            RpgProfile profile = profiles.computeIfAbsent(uuid, ignored -> loadProfile(uuid, latestName));
            return action.apply(profile);
        }
    }

    public RpgProfile profileSnapshot(Player player) {
        UUID uuid = player.getUniqueId();
        synchronized (profileLocks.computeIfAbsent(uuid, ignored -> new Object())) {
            RpgProfile profile = profiles.computeIfAbsent(uuid, ignored -> loadProfile(uuid, player.getName()));
            return profile.copy();
        }
    }

    public <T> T withGuild(String name, Function<RpgGuild, T> action) {
        String key = normalizeGuild(name);
        synchronized (guildLocks.computeIfAbsent(key, ignored -> new Object())) {
            RpgGuild guild = guilds.computeIfAbsent(key, ignored -> loadGuild(key));
            long before = guild.getUpdatedAt();
            T value = action.apply(guild);
            if (guild.getUpdatedAt() != before) {
                dirtyGuilds.add(key);
            }
            return value;
        }
    }

    public Optional<RpgGuild> getGuild(String name) {
        String key = normalizeGuild(name);
        synchronized (guildLocks.computeIfAbsent(key, ignored -> new Object())) {
            RpgGuild guild = guilds.computeIfAbsent(key, ignored -> loadGuild(key));
            if (guild.getOwnerUuid().isBlank() && guild.getMembersView().isEmpty()) {
                return Optional.empty();
            }
            return Optional.of(guild);
        }
    }

    public void flushDirty() {
        List<UUID> profileIds = collectDirtyProfilesForFlush();
        List<String> guildKeys = collectDirtyGuildsForFlush();
        for (UUID uuid : profileIds) {
            flushPlayer(uuid);
        }
        for (String key : guildKeys) {
            flushGuild(key);
        }
    }

    private List<UUID> collectDirtyProfilesForFlush() {
        int limit = Math.max(50, persistence.getInt("write_policy.max_profiles_per_flush", 500));
        List<UUID> selected = new ArrayList<>(Math.min(dirtyProfiles.size(), limit));
        for (UUID uuid : dirtyProfiles) {
            selected.add(uuid);
            if (selected.size() >= limit) {
                break;
            }
        }
        return selected;
    }

    private List<String> collectDirtyGuildsForFlush() {
        int limit = Math.max(20, persistence.getInt("write_policy.max_guilds_per_flush", 200));
        List<String> selected = new ArrayList<>(Math.min(dirtyGuilds.size(), limit));
        for (String guildKey : dirtyGuilds) {
            selected.add(guildKey);
            if (selected.size() >= limit) {
                break;
            }
        }
        return selected;
    }

    public void flushPlayer(UUID uuid) {
        RpgProfile snapshot;
        long version;
        long expectedStoredVersion;
        synchronized (profileLocks.computeIfAbsent(uuid, ignored -> new Object())) {
            RpgProfile profile = profiles.get(uuid);
            if (profile == null) {
                dirtyProfiles.remove(uuid);
                return;
            }
            version = profile.getUpdatedAt();
            Long flushed = lastFlushedProfileVersion.get(uuid);
            if (flushed != null && flushed >= version) {
                dirtyProfiles.remove(uuid);
                return;
            }
            expectedStoredVersion = flushed == null ? 0L : flushed;
            snapshot = profile.copy();
        }
        if (!persistProfileSnapshot(uuid, snapshot, expectedStoredVersion)) {
            return;
        }
        synchronized (profileLocks.computeIfAbsent(uuid, ignored -> new Object())) {
            RpgProfile live = profiles.get(uuid);
            if (live == null || live.getUpdatedAt() == version) {
                dirtyProfiles.remove(uuid);
                lastFlushedProfileVersion.put(uuid, version);
            }
        }
    }

    public void flushGuild(String guildKey) {
        String key = normalizeGuild(guildKey);
        RpgGuild snapshot;
        long version;
        long expectedStoredVersion;
        synchronized (guildLocks.computeIfAbsent(key, ignored -> new Object())) {
            RpgGuild guild = guilds.get(key);
            if (guild == null) {
                dirtyGuilds.remove(key);
                return;
            }
            version = guild.getUpdatedAt();
            Long flushed = lastFlushedGuildVersion.get(key);
            if (flushed != null && flushed >= version) {
                dirtyGuilds.remove(key);
                return;
            }
            expectedStoredVersion = flushed == null ? 0L : flushed;
            snapshot = guild.copy();
        }
        if (!persistGuildSnapshot(key, snapshot, expectedStoredVersion)) {
            return;
        }
        synchronized (guildLocks.computeIfAbsent(key, ignored -> new Object())) {
            RpgGuild live = guilds.get(key);
            if (live == null || live.getUpdatedAt() == version) {
                dirtyGuilds.remove(key);
                lastFlushedGuildVersion.put(key, version);
            }
        }
    }

    private boolean persistProfileSnapshot(UUID uuid, RpgProfile snapshot, long expectedStoredVersion) {
        PersistOutcome authoritative = persistProfileAuthoritatively(snapshot, expectedStoredVersion);
        if (authoritative == PersistOutcome.UNAVAILABLE) {
            enterSafeMode("MySQL backend unavailable");
            return false;
        }
        if (authoritative == PersistOutcome.CONFLICT) {
            synchronized (profileLocks.computeIfAbsent(uuid, ignored -> new Object())) {
                profiles.put(uuid, loadProfile(uuid, snapshot.getLastName()));
                dirtyProfiles.add(uuid);
            }
            writeAudit("profile_conflict", uuid + ":stale_version=" + snapshot.getUpdatedAt());
            return false;
        }
        if (persistence.getBoolean("local_fallback.enabled", true)) {
            writeYaml(profilePath(uuid), snapshot.toYaml().saveToString());
        }
        return true;
    }

    private boolean persistGuildSnapshot(String key, RpgGuild snapshot, long expectedStoredVersion) {
        PersistOutcome authoritative = persistGuildAuthoritatively(snapshot, expectedStoredVersion);
        if (authoritative == PersistOutcome.UNAVAILABLE) {
            enterSafeMode("MySQL backend unavailable");
            return false;
        }
        if (authoritative == PersistOutcome.CONFLICT) {
            String normalized = normalizeGuild(key);
            synchronized (guildLocks.computeIfAbsent(normalized, ignored -> new Object())) {
                guilds.put(normalized, loadGuild(normalized));
                dirtyGuilds.add(normalized);
            }
            writeAudit("guild_conflict", normalized + ":stale_version=" + snapshot.getUpdatedAt());
            return false;
        }
        if (persistence.getBoolean("local_fallback.enabled", true)) {
            writeYaml(guildPath(key), snapshot.toYaml().saveToString());
        }
        return true;
    }

    public void writeMetricSnapshot(String serverSpecificContent) {
        ensurePath(metricsDir);
        Path path = metricsDir.resolve("runtime_" + serverName + ".prom");
        writeYaml(path, serverSpecificContent);
    }

    public void writeAtomicFile(Path path, String contents) {
        writeYaml(path, contents);
    }

    public void writeAudit(String category, String message) {
        String fileName = "audit-" + LocalDate.now(ZoneId.systemDefault()) + ".log";
        String line = System.currentTimeMillis() + "|" + serverName + "|" + category + "|" + message + System.lineSeparator();
        Runnable writer = () -> appendAuditLine(fileName, line);
        if (plugin.isEnabled() && Bukkit.isPrimaryThread()) {
            Bukkit.getScheduler().runTaskAsynchronously(plugin, writer);
            return;
        }
        writer.run();
    }

    private void appendAuditLine(String fileName, String line) {
        ensurePath(auditDir);
        Path path = auditDir.resolve(fileName);
        try {
            if (Files.exists(path)) {
                Files.writeString(path, line, StandardCharsets.UTF_8, java.nio.file.StandardOpenOption.APPEND);
            } else {
                Files.writeString(path, line, StandardCharsets.UTF_8, java.nio.file.StandardOpenOption.CREATE);
            }
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to write audit log: " + exception.getMessage());
        }
    }

    public String profileSummary(Player player) {
        return withProfileRead(player.getUniqueId(), player.getName(), profile -> {
            String guildText = profile.getGuildName().isBlank() ? "none" : profile.getGuildName();
            String activeDungeon = profile.getActiveDungeon().isBlank() ? "none" : profile.getActiveDungeon() + " (kills=" + profile.getActiveDungeonKills() + ")";
            List<String> gear = new ArrayList<>();
            for (Map.Entry<String, String> entry : profile.getGearTiersView().entrySet()) {
                gear.add(entry.getKey() + ":" + entry.getValue());
            }
            return color("&6Profile &7role=&e" + serverRole
                + " &7gold=&e" + money(profile.getGold())
                + " &7guild=&e" + guildText
                + " &7dungeon=&e" + activeDungeon
                + " &7gear=&e" + String.join(", ", gear)
                + " &7inventory=&e" + String.join(", ", profile.inventorySummary(6))
            );
        });
    }

    public String walletSummary(Player player) {
        return withProfileRead(player.getUniqueId(), player.getName(), profile -> color("&6Wallet &7gold=&e" + money(profile.getGold()) + " &7items=&e" + String.join(", ", profile.inventorySummary(8))));
    }

    public String skillSummary(Player player) {
        return withProfileRead(player.getUniqueId(), player.getName(), profile -> {
            List<String> parts = new ArrayList<>();
            ConfigurationSection skillSection = skills.getConfigurationSection("");
            if (skillSection != null) {
                for (String skillId : skillSection.getKeys(false)) {
                    int level = skillLevel(profile, skillId);
                    parts.add(skillId + " Lv." + level + " (xp=" + (int) profile.getSkillXp(skillId) + ")");
                }
            }
            return color("&6Skills &7" + String.join(" &8| &7", parts));
        });
    }

    public List<String> questOverview(Player player) {
        return withProfileRead(player.getUniqueId(), player.getName(), profile -> {
            List<String> lines = new ArrayList<>();
            ConfigurationSection section = quests.getConfigurationSection("");
            if (section == null) {
                lines.add(color("&cNo quest configuration loaded."));
                return lines;
            }
            for (String questId : section.getKeys(false)) {
                lines.add(questStatusLine(profile, questId));
            }
            return lines;
        });
    }

    public OperationResult acceptQuest(Player player, String questId) {
        if (!quests.contains(questId)) {
            return new OperationResult(false, color("&cUnknown quest: " + questId));
        }
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Quest changes paused."));
        }
        return withProfile(player, profile -> {
            long cooldownUntil = profile.getQuestCooldown(questId);
            if (cooldownUntil > System.currentTimeMillis()) {
                return new OperationResult(false, color("&cQuest on cooldown for " + secondsRemaining(cooldownUntil) + "s."));
            }
            if (profile.isQuestAccepted(questId)) {
                return new OperationResult(false, color("&eQuest already accepted."));
            }
            if (!quests.getBoolean(questId + ".repeatable", false) && profile.isQuestCompleted(questId)) {
                return new OperationResult(false, color("&eQuest already completed."));
            }
            profile.acceptQuest(questId);
            syncCollectQuestProgress(profile);
            writeAudit("quest_accept", player.getUniqueId() + ":" + questId);
            return new OperationResult(true, color("&aAccepted quest &e" + questId));
        });
    }

    public OperationResult turnInQuest(Player player, String questId) {
        if (!quests.contains(questId)) {
            return new OperationResult(false, color("&cUnknown quest: " + questId));
        }
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Quest turn-in paused."));
        }
        return withProfile(player, profile -> {
            if (!profile.isQuestAccepted(questId)) {
                return new OperationResult(false, color("&eQuest not accepted."));
            }
            int target = quests.getInt(questId + ".amount", 1);
            if (profile.getQuestProgress(questId) < target) {
                return new OperationResult(false, color("&cQuest incomplete: " + profile.getQuestProgress(questId) + "/" + target));
            }
            String objective = quests.getString(questId + ".objective", "kill");
            if ("collect".equalsIgnoreCase(objective)) {
                String requiredItem = quests.getString(questId + ".item", "");
                if (!profile.removeItem(requiredItem, target)) {
                    syncCollectQuestProgress(profile);
                    return new OperationResult(false, color("&cQuest items must still be present at turn-in."));
                }
            }
            double rewardGold = quests.getDouble(questId + ".reward.gold", 0.0D);
            profile.addGold(rewardGold);
            for (Map.Entry<String, Integer> entry : intMap(quests.getConfigurationSection(questId + ".reward.items")).entrySet()) {
                profile.addItem(entry.getKey(), entry.getValue());
            }
            int rewardXp = quests.getInt(questId + ".reward.xp", 0);
            applyQuestRewardXp(profile, objective, rewardXp);
            appendLedgerMutation(profile.getUuid(), "quest_turnin", questId, rewardGold, intMap(quests.getConfigurationSection(questId + ".reward.items")));
            if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                return new OperationResult(false, color("&cQuest reward commit delayed. Try again."));
            }
            if (quests.getBoolean(questId + ".repeatable", false)) {
                int cooldownHours = quests.getInt(questId + ".cooldown_hours", 0);
                if (cooldownHours > 0) {
                    profile.setQuestCooldown(questId, System.currentTimeMillis() + cooldownHours * 3_600_000L);
                }
            } else {
                profile.markQuestCompleted(questId);
            }
            profile.abandonQuest(questId);
            syncCollectQuestProgress(profile);
            writeAudit("quest_turnin", player.getUniqueId() + ":" + questId + ":gold=" + rewardGold);
            return new OperationResult(true, color("&aQuest complete: &e" + questId + " &7reward=&e" + money(rewardGold)));
        });
    }

    public KillReward handleMobKill(Player killer, Entity entity) {
        String mobId = resolveMobId(entity);
        if (mobId == null || resolveBossId(entity) != null) {
            return new KillReward(false, "", 0.0D, Collections.emptyMap(), "");
        }
        if (!canClaimReservedEntityKill(killer, entity)) {
            return new KillReward(true, mobId, 0.0D, Collections.emptyMap(), color("&cThis dungeon instance is reserved for another player."));
        }
        if (safeMode) {
            return new KillReward(true, mobId, 0.0D, Collections.emptyMap(), color("&cBackend safe mode active. Rewards paused."));
        }
        markManagedEntityRemoved(entity);
        String nonce = "mob-kill:" + entity.getUniqueId();
        return withProfile(killer, profile -> {
            if (profile.isNonceSeen(nonce, nonceWindowMillis())) {
                return new KillReward(false, mobId, 0.0D, Collections.emptyMap(), "");
            }
            profile.markNonce(nonce);
            profile.incrementKillCount(mobId);
            double goldReward = configuredMobGold(mobId);
            profile.addGold(goldReward);
            Map<String, Integer> rolled = rollConfiguredDrops(mobs.getConfigurationSection(mobId + ".drops"));
            for (Map.Entry<String, Integer> entry : rolled.entrySet()) {
                profile.addItem(entry.getKey(), entry.getValue());
            }
            appendLedgerMutation(profile.getUuid(), "mob_kill", mobId, goldReward, rolled);
            if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                return new KillReward(true, mobId, 0.0D, Collections.emptyMap(), color("&cReward commit delayed. Try again."));
            }
            awardSkillXp(profile, "combat", "mob_kill");
            updateQuestProgressForKill(profile, mobId, false, "");
            syncCollectQuestProgress(profile);
            writeAudit("mob_kill", killer.getUniqueId() + ":" + mobId + ":gold=" + goldReward + ":items=" + rolled);
            String msg = color("&aKill reward &7mob=&e" + mobId + " &7gold=&e" + money(goldReward) + rewardSuffix(rolled));
            lastMobRewardAt.put(killer.getUniqueId(), System.currentTimeMillis());
            return new KillReward(true, mobId, goldReward, rolled, msg);
        });
    }

    public BossReward handleBossKill(Player killer, Entity entity) {
        String bossId = resolveBossId(entity);
        String instanceId = tagValue(entity, "rpg_instance:");
        if (bossId == null) {
            return new BossReward(false, "", false, 0.0D, Collections.emptyMap(), "");
        }
        if (!canClaimReservedEntityKill(killer, entity)) {
            return new BossReward(true, bossId, false, 0.0D, Collections.emptyMap(), color("&cThis dungeon instance is reserved for another player."));
        }
        if (safeMode) {
            return new BossReward(true, bossId, false, 0.0D, Collections.emptyMap(), color("&cBackend safe mode active. Rewards paused."));
        }
        markManagedEntityRemoved(entity);
        String nonce = "boss-kill:" + entity.getUniqueId();
        return withProfile(killer, profile -> {
            if (profile.isNonceSeen(nonce, nonceWindowMillis())) {
                return new BossReward(false, bossId, false, 0.0D, Collections.emptyMap(), "");
            }
            profile.markNonce(nonce);
            profile.incrementKillCount(bossId);
            long lockoutUntil = profile.getBossLockout(bossId);
            boolean rewardOncePerLockout = exploit.getBoolean("progression.boss_reward_once_per_lockout", true);
            if (rewardOncePerLockout && lockoutUntil > System.currentTimeMillis()) {
                updateQuestProgressForKill(profile, "", true, bossId);
                awardSkillXp(profile, "combat", "boss_kill");
                return new BossReward(true, bossId, false, 0.0D, Collections.emptyMap(), color("&eBoss defeated but rewards are locked for " + secondsRemaining(lockoutUntil) + "s."));
            }
            Map<String, Integer> itemsGranted = new LinkedHashMap<>();
            itemsGranted.putAll(intMap(bosses.getConfigurationSection(bossId + ".drops.guaranteed")));
            for (Map.Entry<String, Integer> entry : itemsGranted.entrySet()) {
                profile.addItem(entry.getKey(), entry.getValue());
            }
            Map<String, Integer> rareDrops = rollRareBossDrops(bosses.getConfigurationSection(bossId + ".drops.rare"));
            for (Map.Entry<String, Integer> entry : rareDrops.entrySet()) {
                profile.addItem(entry.getKey(), entry.getValue());
                itemsGranted.merge(entry.getKey(), entry.getValue(), Integer::sum);
            }
            String bonusKey = bossId + "_first_daily_bonus";
            double bonusGold = 0.0D;
            String today = dailyDateKey(System.currentTimeMillis());
            if (!today.equals(profile.getBossDailyBonusDate(bossId)) && economy.contains("faucets.bosses." + bonusKey)) {
                bonusGold = economy.getDouble("faucets.bosses." + bonusKey, 0.0D);
                profile.addGold(bonusGold);
                profile.setBossDailyBonusDate(bossId, today);
            }
            int lockoutHours = bosses.getInt(bossId + ".summon.lockout_hours", 0);
            profile.setBossLockout(bossId, System.currentTimeMillis() + lockoutHours * 3_600_000L);
            appendLedgerMutation(profile.getUuid(), "boss_kill", bossId, bonusGold, itemsGranted);
            if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                return new BossReward(true, bossId, false, 0.0D, Collections.emptyMap(), color("&cReward commit delayed. Try again."));
            }
            awardSkillXp(profile, "combat", "boss_kill");
            updateQuestProgressForKill(profile, "", true, bossId);
            syncCollectQuestProgress(profile);
            DungeonInstanceState encounter = loadDungeonInstance(instanceId);
            if (encounter != null && encounter.type == InstanceType.BOSS_ENCOUNTER) {
                instanceOrchestrator.beginEgress(encounter);
                cleanupDungeonInstance(encounter, "boss_defeated");
            }
            writeAudit("boss_kill", killer.getUniqueId() + ":" + bossId + ":gold=" + bonusGold + ":items=" + itemsGranted);
            String msg = color("&aBoss rewards &7boss=&e" + bossId + rewardSuffix(itemsGranted) + (bonusGold > 0.0D ? " &7bonus=&e" + money(bonusGold) : ""));
            return new BossReward(true, bossId, true, bonusGold, itemsGranted, msg);
        });
    }

    public DungeonStart startDungeon(Player player, String dungeonId) {
        if (safeMode) {
            return new DungeonStart(false, dungeonId, 0, color("&cBackend safe mode active. Dungeon entry paused."));
        }
        if (!"instance".equalsIgnoreCase(serverRole)) {
            return new DungeonStart(false, dungeonId, 0, color("&cDungeon entry only allowed on instance servers."));
        }
        if (!dungeons.contains(dungeonId)) {
            return new DungeonStart(false, dungeonId, 0, color("&cUnknown dungeon: " + dungeonId));
        }
        return withProfile(player, profile -> {
            if (!profile.getActiveDungeon().isBlank()) {
                return new DungeonStart(false, dungeonId, 0, color("&eAlready inside dungeon &6" + profile.getActiveDungeon()));
            }
            long cooldownUntil = profile.getDungeonCooldown(dungeonId);
            if (cooldownUntil > System.currentTimeMillis()) {
                return new DungeonStart(false, dungeonId, 0, color("&cDungeon on cooldown for " + secondsRemaining(cooldownUntil) + "s."));
            }
            Map<String, Integer> requirements = intMap(dungeons.getConfigurationSection(dungeonId + ".entry_requirements"));
            if (!profile.hasItems(requirements)) {
                return new DungeonStart(false, dungeonId, 0, color("&cMissing entry materials: " + missingItems(profile, requirements)));
            }
            double fee = dungeons.getDouble(dungeonId + ".entry_fee_gold", 0.0D);
            if (profile.getGold() + 0.000001D < fee) {
                return new DungeonStart(false, dungeonId, 0, color("&cNeed " + money(fee) + " gold for entry."));
            }
            DungeonInstanceState instance = createDungeonInstance(player.getUniqueId(), dungeonId, Set.of(player.getUniqueId()));
            World world = ensureDungeonWorld(instance);
            if (world == null) {
                cleanupDungeonInstance(instance, "world_create_failed");
                return new DungeonStart(false, dungeonId, 0, color("&cFailed to prepare a private dungeon instance."));
            }
            if (!profile.spendGold(fee)) {
                cleanupDungeonInstance(instance, "entry_cost_recheck_failed");
                return new DungeonStart(false, dungeonId, 0, color("&cNeed " + money(fee) + " gold for entry."));
            }
            removeItems(profile, requirements);
            appendLedgerMutation(profile.getUuid(), "dungeon_entry_cost", dungeonId, -fee, negativeItemMap(requirements));
            if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                profile.addGold(fee);
                addItems(profile, requirements);
                cleanupDungeonInstance(instance, "durability_boundary");
                return new DungeonStart(false, dungeonId, 0, color("&cDungeon entry commit delayed. Try again."));
            }
            profile.setActiveDungeon(dungeonId);
            profile.setActiveDungeonInstanceId(instance.instanceId);
            profile.setActiveDungeonWorld(instance.worldName);
            profile.setActiveDungeonKills(0);
            profile.setActiveDungeonBossSpawned(false);
            profile.setActiveDungeonStartedAt(System.currentTimeMillis());
            awardSkillXp(profile, "exploration", "dungeon_entry");
            syncCollectQuestProgress(profile);
            clearWorldEntities(world);
            Location entry = dungeonEntryLocation(world);
            player.teleport(entry);
            int spawnTotal = spawnDungeonWave(entry, player, dungeonId, instance.instanceId);
            instanceOrchestrator.activate(instance);
            writeSession(profile, true);
            writeAudit("dungeon_enter", player.getUniqueId() + ":" + dungeonId + ":fee=" + fee + ":spawned=" + spawnTotal);
            return new DungeonStart(true, dungeonId, spawnTotal, color("&aEntered dungeon &e" + dungeonId + " &7spawned=&e" + spawnTotal));
        });
    }

    public OperationResult abandonDungeon(Player player) {
        return withProfile(player, profile -> {
            if (profile.getActiveDungeon().isBlank()) {
                return new OperationResult(false, color("&eNo active dungeon."));
            }
            String dungeonId = profile.getActiveDungeon();
            profile.setDungeonCooldown(dungeonId, System.currentTimeMillis() + exploit.getLong("progression.dungeon_reentry_cooldown_seconds", 15L) * 1000L);
            teleportToPrimaryWorldSpawn(player);
            instanceOrchestrator.beginEgress(loadDungeonInstance(profile.getActiveDungeonInstanceId()));
            cleanupOwnedDungeonInstance(player.getUniqueId(), "abandon");
            profile.clearActiveDungeon();
            writeSession(profile, true);
            writeAudit("dungeon_abandon", player.getUniqueId() + ":" + dungeonId);
            return new OperationResult(true, color("&eAbandoned dungeon &6" + dungeonId));
        });
    }

    public String dungeonStatus(Player player) {
        return withProfileRead(player.getUniqueId(), player.getName(), profile -> {
            if (profile.getActiveDungeon().isBlank()) {
                return color("&eNo active dungeon.");
            }
            return color("&6Dungeon &7id=&e" + profile.getActiveDungeon()
                + " &7instance=&e" + (profile.getActiveDungeonInstanceId().isBlank() ? "none" : profile.getActiveDungeonInstanceId())
                + " &7kills=&e" + profile.getActiveDungeonKills()
                + " &7boss=&e" + profile.isActiveDungeonBossSpawned());
        });
    }

    public DungeonProgress handleDungeonMobKill(Player player, Entity entity) {
        String dungeonId = tagValue(entity, "rpg_dungeon:");
        String instanceId = tagValue(entity, "rpg_instance:");
        String bossTag = tagValue(entity, "rpg_dungeon_boss:");
        if (dungeonId == null || bossTag != null) {
            return new DungeonProgress(false, false, "");
        }
        if (!canClaimReservedEntityKill(player, entity)) {
            return new DungeonProgress(true, false, color("&cKill denied outside your reserved instance."));
        }
        String mobId = resolveMobId(entity);
        return withProfile(player, profile -> {
            if (!dungeonId.equals(profile.getActiveDungeon())) {
                return new DungeonProgress(false, false, "");
            }
            if (!Objects.equals(instanceId, profile.getActiveDungeonInstanceId())) {
                return new DungeonProgress(true, false, color("&cKill denied outside your reserved instance."));
            }
            List<String> trash = dungeons.getStringList(dungeonId + ".trash_mobs");
            if (mobId == null || !trash.contains(mobId)) {
                return new DungeonProgress(false, false, "");
            }
            profile.incrementActiveDungeonKills();
            int requiredKills = Math.max(6, trash.size() * 3);
            if (!profile.isActiveDungeonBossSpawned() && profile.getActiveDungeonKills() >= requiredKills) {
                String bossId = dungeons.getString(dungeonId + ".boss", "");
                LivingEntity boss = spawnConfiguredBoss(player.getLocation().add(0.0D, 0.0D, 4.0D), bossId, player, dungeonId, profile.getActiveDungeonInstanceId());
                if (boss != null) {
                    profile.setActiveDungeonBossSpawned(true);
                    writeAudit("dungeon_boss_spawn", player.getUniqueId() + ":" + dungeonId + ":" + bossId);
                    return new DungeonProgress(true, true, color("&cDungeon boss spawned: &6" + bossId));
                }
            }
            return new DungeonProgress(true, false, color("&7Dungeon progress &e" + profile.getActiveDungeonKills() + " kills"));
        });
    }

    public DungeonCompletion handleDungeonBossKill(Player player, Entity entity) {
        String dungeonId = tagValue(entity, "rpg_dungeon_boss:");
        String instanceId = tagValue(entity, "rpg_instance:");
        if (dungeonId == null) {
            return new DungeonCompletion(false, false, "", 0.0D, Collections.emptyMap(), "");
        }
        if (!canClaimReservedEntityKill(player, entity)) {
            return new DungeonCompletion(true, false, dungeonId, 0.0D, Collections.emptyMap(), color("&cBoss denied outside your reserved instance."));
        }
        String bossId = resolveBossId(entity);
        return withProfile(player, profile -> {
            if (!dungeonId.equals(profile.getActiveDungeon())) {
                return new DungeonCompletion(false, false, dungeonId, 0.0D, Collections.emptyMap(), "");
            }
            if (!Objects.equals(instanceId, profile.getActiveDungeonInstanceId())) {
                return new DungeonCompletion(true, false, dungeonId, 0.0D, Collections.emptyMap(), color("&cBoss denied outside your reserved instance."));
            }
            String completionClaimKey = "dungeon-complete:" + profile.getUuid() + ":" + instanceId;
            if (profile.hasClaimedOperation(completionClaimKey)) {
                rewardDuplicateSuppressed.incrementAndGet();
                return new DungeonCompletion(true, false, dungeonId, 0.0D, Collections.emptyMap(), color("&eDungeon rewards already claimed for this run."));
            }
            String requiredBoss = dungeons.getString(dungeonId + ".boss", "");
            if (!requiredBoss.equals(bossId)) {
                return new DungeonCompletion(false, false, dungeonId, 0.0D, Collections.emptyMap(), "");
            }
            profile.markClaimedOperation(completionClaimKey);
            profile.pruneClaimedOperations(claimRetentionMillis());
            DungeonInstanceState activeInstance = loadDungeonInstance(profile.getActiveDungeonInstanceId());
            instanceOrchestrator.resolve(activeInstance);
            Map<String, Integer> rewards = intMap(dungeons.getConfigurationSection(dungeonId + ".completion_rewards"));
            for (Map.Entry<String, Integer> entry : rewards.entrySet()) {
                profile.addItem(entry.getKey(), entry.getValue());
            }
            String bonusKey = dungeonId + "_clear_bonus";
            double goldReward = economy.getDouble("faucets.dungeons." + bonusKey, 0.0D);
            profile.addGold(goldReward);
            appendLedgerMutation(profile.getUuid(), "dungeon_complete", dungeonId, goldReward, rewards);
            if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                profile.clearClaimedOperation(completionClaimKey);
                return new DungeonCompletion(true, false, dungeonId, 0.0D, Collections.emptyMap(), color("&cReward commit delayed. Try again."));
            }
            instanceOrchestrator.rewardCommit(activeInstance);
            profile.setDungeonCooldown(dungeonId, System.currentTimeMillis() + dungeons.getLong(dungeonId + ".repeat_cooldown_seconds", 30L) * 1000L);
            teleportToPrimaryWorldSpawn(player);
            instanceOrchestrator.beginEgress(activeInstance);
            cleanupOwnedDungeonInstance(player.getUniqueId(), "complete");
            profile.clearActiveDungeon();
            awardSkillXp(profile, "combat", "dungeon_clear");
            updateQuestProgressForDungeonClear(profile, dungeonId);
            syncCollectQuestProgress(profile);
            writeSession(profile, true);
            writeAudit("dungeon_complete", player.getUniqueId() + ":" + dungeonId + ":gold=" + goldReward + ":items=" + rewards);
            return new DungeonCompletion(true, true, dungeonId, goldReward, rewards, color("&aDungeon cleared &e" + dungeonId + rewardSuffix(rewards) + " &7bonus=&e" + money(goldReward)));
        });
    }

    public OperationResult grantEventBonusReward(Player player, String eventId, String nonce, double gold, String itemId, int amount, boolean grantItem) {
        return withProfile(player, profile -> {
            if (nonce == null || nonce.isBlank()) {
                return new OperationResult(false, color("&cMissing reward nonce."));
            }
            String opKey = "event-bonus:" + eventId + ":" + nonce;
            if (profile.hasClaimedOperation(opKey)) {
                rewardDuplicateSuppressed.incrementAndGet();
                return new OperationResult(true, color("&7Duplicate event reward suppressed."));
            }
            profile.markClaimedOperation(opKey);
            profile.pruneClaimedOperations(claimRetentionMillis());
            Map<String, Integer> grantedItems = Collections.emptyMap();
            profile.addGold(gold);
            if (grantItem && itemId != null && !itemId.isBlank() && amount > 0) {
                String normalized = itemId.toLowerCase(Locale.ROOT);
                profile.addItem(normalized, amount);
                grantedItems = Map.of(normalized, amount);
            }
            appendLedgerMutation(profile.getUuid(), "event_bonus_reward", eventId + ":" + nonce, gold, grantedItems);
            if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                profile.clearClaimedOperation(opKey);
                return new OperationResult(false, color("&cEvent bonus commit delayed. Try again."));
            }
            awardSkillXp(profile, "combat", "mob_kill");
            syncCollectQuestProgress(profile);
            writeAudit("event_bonus_reward", player.getUniqueId() + ":" + eventId + ":" + nonce + ":gold=" + gold + ":items=" + grantedItems);
            return new OperationResult(true, color("&dEvent bonus: " + eventId));
        });
    }

    public BossSummonResult summonBoss(Player player, String bossId, boolean useGuildBank) {
        if (safeMode) {
            return new BossSummonResult(false, bossId, color("&cBackend safe mode active. Boss summoning paused."), null);
        }
        if (!bosses.contains(bossId)) {
            return new BossSummonResult(false, bossId, color("&cUnknown boss: " + bossId), null);
        }
        if (!"boss".equalsIgnoreCase(serverRole) && !"instance".equalsIgnoreCase(serverRole)) {
            return new BossSummonResult(false, bossId, color("&cBoss summoning only allowed on boss or instance servers."), null);
        }
        String activeDungeon = withProfile(player, profile -> profile.getActiveDungeon());
        if ("instance".equalsIgnoreCase(serverRole)) {
            if (activeDungeon.isBlank()) {
                return new BossSummonResult(false, bossId, color("&cBoss summons on instance servers require an active dungeon."), null);
            }
            String dungeonBoss = dungeons.getString(activeDungeon + ".boss", "");
            if (!bossId.equals(dungeonBoss)) {
                return new BossSummonResult(false, bossId, color("&cActive dungeon requires boss &6" + dungeonBoss), null);
            }
        }
        final String dungeonIdForBoss = activeDungeon.isBlank() ? null : activeDungeon;

        if (!useGuildBank) {
            return withProfile(player, profile -> {
                String operationKey = buildSummonOperationKey(profile.getUuid(), bossId, dungeonIdForBoss);
                String refundReference = bossId + ":refund:" + operationKey;
                Map<String, Integer> req = intMap(bosses.getConfigurationSection(bossId + ".summon.required_items"));
                if (!profile.hasItems(req)) {
                    return new BossSummonResult(false, bossId, color("&cMissing summon materials: " + missingItems(profile, req)), null);
                }
                double goldCost = bosses.getDouble(bossId + ".summon.gold_cost", 0.0D);
                if (!profile.spendGold(goldCost)) {
                    return new BossSummonResult(false, bossId, color("&cNeed " + money(goldCost) + " gold to summon."), null);
                }
                removeItems(profile, req);
                appendLedgerMutation(profile.getUuid(), "boss_summon_personal", bossId + ":" + operationKey, -goldCost, negativeItemMap(req));
                if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                    profile.addGold(goldCost);
                    addItems(profile, req);
                    return new BossSummonResult(false, bossId, color("&cSummon commit delayed. Try again."), null);
                }

                DungeonInstanceState encounterInstance = null;
                if (dungeonIdForBoss == null) {
                    encounterInstance = instanceOrchestrator.allocateBossEncounter(player.getUniqueId(), bossId, Set.of(player.getUniqueId()));
                    World encounterWorld = instanceOrchestrator.bootInstanceWorld(encounterInstance);
                    if (encounterWorld == null) {
                        profile.addGold(goldCost);
                        addItems(profile, req);
                        cleanupDungeonInstance(encounterInstance, "boss_encounter_world_failed");
                        return new BossSummonResult(false, bossId, color("&cFailed to allocate boss encounter instance."), null);
                    }
                    instanceOrchestrator.activate(encounterInstance);
                    Location entry = dungeonEntryLocation(encounterWorld);
                    if (entry != null) {
                        player.teleport(entry);
                    }
                }

                Location spawnOrigin = player.getLocation().add(0.0D, 0.0D, 5.0D);
                String encounterInstanceId = encounterInstance == null ? null : encounterInstance.instanceId;
                LivingEntity entity = spawnConfiguredBoss(spawnOrigin, bossId, player, dungeonIdForBoss, encounterInstanceId);
                if (entity == null) {
                    profile.addGold(goldCost);
                    addItems(profile, req);
                    appendLedgerMutation(profile.getUuid(), "boss_summon_personal_refund", refundReference, goldCost, req);
                    if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), profile.getGuildName(), resolveGuildVersion(profile.getGuildName()))) {
                        return new BossSummonResult(false, bossId, color("&cFailed to spawn boss and refund commit delayed. Contact staff."), null);
                    }
                    if (encounterInstance != null) {
                        cleanupDungeonInstance(encounterInstance, "boss_spawn_failed");
                    }
                    return new BossSummonResult(false, bossId, color("&cFailed to spawn boss."), null);
                }
                writeAudit("boss_summon", player.getUniqueId() + ":" + bossId + ":personal:instance=" + (encounterInstance == null ? "shared" : encounterInstance.instanceId));
                return new BossSummonResult(true, bossId, color("&cBoss summoned: &6" + bossId), entity);
            });
        }

        return withProfile(player, profile -> {
            if (profile.getGuildName().isBlank()) {
                return new BossSummonResult(false, bossId, color("&cYou are not in a guild."), null);
            }
            Optional<RpgGuild> guildOptional = getGuild(profile.getGuildName());
            if (guildOptional.isEmpty()) {
                return new BossSummonResult(false, bossId, color("&cGuild data missing."), null);
            }
            RpgGuild guild = guildOptional.get();
            synchronized (guildLocks.computeIfAbsent(normalizeGuild(guild.getName()), ignored -> new Object())) {
                String operationKey = buildSummonOperationKey(profile.getUuid(), bossId, dungeonIdForBoss);
                String refundReference = bossId + ":refund:" + operationKey;
                Map<String, Integer> req = intMap(bosses.getConfigurationSection(bossId + ".summon.required_items"));
                if (req.keySet().stream().anyMatch(this::isBoundMaterial)) {
                    return new BossSummonResult(false, bossId, color("&cBound summon materials cannot be sourced from guild storage."), null);
                }
                for (Map.Entry<String, Integer> entry : req.entrySet()) {
                    if (guild.getBankItemCount(entry.getKey()) < entry.getValue()) {
                        return new BossSummonResult(false, bossId, color("&cGuild bank missing " + entry.getKey() + " x" + entry.getValue()), null);
                    }
                }
                double goldCost = bosses.getDouble(bossId + ".summon.gold_cost", 0.0D);
                if (!guild.spendBankGold(goldCost)) {
                    return new BossSummonResult(false, bossId, color("&cGuild bank needs " + money(goldCost) + " gold."), null);
                }
                for (Map.Entry<String, Integer> entry : req.entrySet()) {
                    guild.removeBankItem(entry.getKey(), entry.getValue());
                }
                dirtyGuilds.add(normalizeGuild(guild.getName()));
                appendLedgerMutation(profile.getUuid(), "boss_summon_guild", bossId + ":" + operationKey, -goldCost, negativeItemMap(req));
                if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), guild.getName(), guild.getUpdatedAt())) {
                    guild.addBankGold(goldCost);
                    for (Map.Entry<String, Integer> entry : req.entrySet()) {
                        guild.addBankItem(entry.getKey(), entry.getValue());
                    }
                    dirtyGuilds.add(normalizeGuild(guild.getName()));
                    return new BossSummonResult(false, bossId, color("&cSummon commit delayed. Try again."), null);
                }

                DungeonInstanceState encounterInstance = null;
                if (dungeonIdForBoss == null) {
                    encounterInstance = instanceOrchestrator.allocateBossEncounter(player.getUniqueId(), bossId, Set.of(player.getUniqueId()));
                    World encounterWorld = instanceOrchestrator.bootInstanceWorld(encounterInstance);
                    if (encounterWorld == null) {
                        guild.addBankGold(goldCost);
                        for (Map.Entry<String, Integer> entry : req.entrySet()) {
                            guild.addBankItem(entry.getKey(), entry.getValue());
                        }
                        dirtyGuilds.add(normalizeGuild(guild.getName()));
                        cleanupDungeonInstance(encounterInstance, "boss_encounter_world_failed");
                        return new BossSummonResult(false, bossId, color("&cFailed to allocate boss encounter instance."), null);
                    }
                    instanceOrchestrator.activate(encounterInstance);
                    Location entry = dungeonEntryLocation(encounterWorld);
                    if (entry != null) {
                        player.teleport(entry);
                    }
                }

                Location spawnOrigin = player.getLocation().add(0.0D, 0.0D, 5.0D);
                String encounterInstanceId = encounterInstance == null ? null : encounterInstance.instanceId;
                LivingEntity entity = spawnConfiguredBoss(spawnOrigin, bossId, player, dungeonIdForBoss, encounterInstanceId);
                if (entity == null) {
                    guild.addBankGold(goldCost);
                    for (Map.Entry<String, Integer> entry : req.entrySet()) {
                        guild.addBankItem(entry.getKey(), entry.getValue());
                    }
                    dirtyGuilds.add(normalizeGuild(guild.getName()));
                    appendLedgerMutation(profile.getUuid(), "guild_bank_refund_failed_summon", refundReference, goldCost, req);
                    if (!commitDurabilityBoundary(profile.getUuid(), profile.getUpdatedAt(), guild.getName(), guild.getUpdatedAt())) {
                        return new BossSummonResult(false, bossId, color("&cFailed to spawn boss and guild refund commit delayed. Contact staff."), null);
                    }
                    if (encounterInstance != null) {
                        cleanupDungeonInstance(encounterInstance, "boss_spawn_failed");
                    }
                    return new BossSummonResult(false, bossId, color("&cFailed to spawn boss."), null);
                }
                writeAudit("boss_summon", player.getUniqueId() + ":" + bossId + ":guild=" + guild.getName() + ":instance=" + (encounterInstance == null ? "shared" : encounterInstance.instanceId));
                return new BossSummonResult(true, bossId, color("&cGuild summoned boss: &6" + bossId), entity);
            }
        });
    }

    public OperationResult sellItem(Player player, String itemId, int amount) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Vendor actions paused."));
        }
        String key = itemId.toLowerCase(Locale.ROOT);
        if (!items.contains("materials." + key)) {
            return new OperationResult(false, color("&cUnknown material: " + itemId));
        }
        if (amount <= 0) {
            return new OperationResult(false, color("&cAmount must be positive."));
        }
        return withProfile(player, profile -> {
            if (profile.getItemCount(key) < amount) {
                return new OperationResult(false, color("&cYou only have " + profile.getItemCount(key) + " of " + key));
            }
            int vendorValue = items.getInt("materials." + key + ".vendor_value", 0);
            if (vendorValue <= 0) {
                return new OperationResult(false, color("&eVendor does not buy this item."));
            }
            profile.removeItem(key, amount);
            double payout = vendorValue * amount;
            profile.addGold(payout);
            appendLedgerMutation(profile.getUuid(), "vendor_sell", key, payout, Map.of(key, -amount));
            syncCollectQuestProgress(profile);
            writeAudit("vendor_sell", player.getUniqueId() + ":" + key + ":" + amount + ":gold=" + payout);
            return new OperationResult(true, color("&aSold &e" + key + " x" + amount + " &7for &e" + money(payout)));
        });
    }

    public OperationResult upgradeGear(Player player, String gearPath) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Upgrades paused."));
        }
        if (!items.contains("gear_paths." + gearPath)) {
            return new OperationResult(false, color("&cUnknown gear path: " + gearPath));
        }
        return withProfile(player, profile -> {
            List<String> upgradePath = items.getStringList("gear_paths." + gearPath + ".upgrade_path");
            if (upgradePath.isEmpty()) {
                return new OperationResult(false, color("&cNo upgrade path configured."));
            }
            String currentTier = profile.getGearTier(gearPath, items.getString("gear_paths." + gearPath + ".starting_tier", upgradePath.getFirst()));
            int idx = upgradePath.indexOf(currentTier);
            if (idx < 0) {
                idx = 0;
            }
            if (idx >= upgradePath.size() - 1) {
                return new OperationResult(false, color("&eGear already at max tier."));
            }
            String nextTier = upgradePath.get(idx + 1);
            Map<String, Integer> req = intMap(items.getConfigurationSection("tiers." + nextTier + ".required_materials"));
            if (!profile.hasItems(req)) {
                return new OperationResult(false, color("&cMissing upgrade materials: " + missingItems(profile, req)));
            }
            double goldCost = items.getDouble("tiers." + nextTier + ".upgrade_cost_gold", 0.0D);
            if (!profile.spendGold(goldCost)) {
                return new OperationResult(false, color("&cNeed " + money(goldCost) + " gold to upgrade."));
            }
            removeItems(profile, req);
            profile.setGearTier(gearPath, nextTier);
            appendLedgerMutation(profile.getUuid(), "gear_upgrade", gearPath + ":" + currentTier + "->" + nextTier, -goldCost, negativeItemMap(req));
            awardSkillXp(profile, "crafting", "gear_upgrade");
            syncCollectQuestProgress(profile);
            writeAudit("gear_upgrade", player.getUniqueId() + ":" + gearPath + ":" + currentTier + "->" + nextTier);
            return new OperationResult(true, color("&aUpgraded &e" + gearPath + " &7to &d" + nextTier));
        });
    }

    public OperationResult travel(Player player, String targetServer) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Travel paused."));
        }
        if (!network.contains("servers." + targetServer)) {
            return new OperationResult(false, color("&cUnknown server: " + targetServer));
        }
        if (targetServer.equals(serverName)) {
            return new OperationResult(false, color("&eYou are already on that server."));
        }
        if (!isTravelAllowed(targetServer)) {
            return new OperationResult(false, color("&cTravel route blocked by production topology."));
        }
        long now = System.currentTimeMillis();
        long previous = lastCommandAt.getOrDefault(player.getUniqueId(), 0L);
        if (now - previous < 1000L) {
            return new OperationResult(false, color("&cTravel rate limited."));
        }
        lastCommandAt.put(player.getUniqueId(), now);

        final String address = network.getString("servers." + targetServer + ".address", "127.0.0.1:25565");
        String[] split = address.split(":", 2);
        if (split.length != 2 || split[0].isBlank()) {
            return new OperationResult(false, color("&cTarget server route is invalid in topology config."));
        }
        try {
            Integer.parseInt(split[1]);
        } catch (NumberFormatException exception) {
            return new OperationResult(false, color("&cTarget server route is invalid in topology config."));
        }
        if (!network.getBoolean("proxy.advanced.bungee_plugin_message_channel", false)) {
            return new OperationResult(false, color("&cProxy routing channel is disabled. Travel is safely blocked."));
        }
        final RpgProfile[] sessionSnapshot = new RpgProfile[1];
        final double[] feeHolder = new double[1];
        final long[] profileVersionHolder = new long[1];
        final long[] guildVersionHolder = new long[1];
        final String[] guildNameHolder = new String[1];
        final String transferId = UUID.randomUUID().toString();
        OperationResult reservation = withProfile(player, profile -> {
            double fee = economy.getDouble("sinks.travel.local_transfer_fee", 0.0D);
            if (!profile.spendGold(fee)) {
                return new OperationResult(false, color("&cNeed " + money(fee) + " gold to travel."));
            }
            profile.incrementTransfers();
            appendLedgerMutation(profile.getUuid(), "travel_fee", serverName + "->" + targetServer, -fee, Collections.emptyMap());
            feeHolder[0] = fee;
            sessionSnapshot[0] = profile.copy();
            profileVersionHolder[0] = profile.getUpdatedAt();
            String guildName = normalizeGuild(profile.getGuildName());
            guildNameHolder[0] = guildName;
            if (!guildName.isBlank()) {
                synchronized (guildLocks.computeIfAbsent(guildName, ignored -> new Object())) {
                    RpgGuild guild = guilds.computeIfAbsent(guildName, ignored -> loadGuild(guildName));
                    guildVersionHolder[0] = guild.getUpdatedAt();
                }
                flushGuild(guildName);
            }
            return new OperationResult(true, "");
        });
        if (!reservation.ok()) {
            return reservation;
        }
        double fee = feeHolder[0];
        long expectedProfileVersion = profileVersionHolder[0];
        long expectedGuildVersion = guildVersionHolder[0];
        String expectedGuildName = guildNameHolder[0] == null ? "" : guildNameHolder[0];
        RpgProfile snapshot = sessionSnapshot[0];
        if (snapshot == null) {
            return new OperationResult(false, color("&cUnable to prepare travel state."));
        }
        freezeMutationAuthority(player.getUniqueId());
        flushPlayer(player.getUniqueId());
        if (lastFlushedProfileVersion.getOrDefault(player.getUniqueId(), 0L) < expectedProfileVersion) {
            unfreezeMutationAuthority(player.getUniqueId());
            withProfile(player, profile -> {
                profile.addGold(fee);
                appendLedgerMutation(profile.getUuid(), "travel_refund", serverName + "->" + targetServer, fee, Collections.emptyMap());
                return null;
            });
            return new OperationResult(false, color("&cTravel blocked until profile persistence catches up."));
        }
        if (!issueTravelTicket(player.getUniqueId(), transferId, targetServer, expectedProfileVersion, expectedGuildName, expectedGuildVersion)) {
            clearTravelTicket(player.getUniqueId());
            unfreezeMutationAuthority(player.getUniqueId());
            withProfile(player, profile -> {
                profile.addGold(fee);
                appendLedgerMutation(profile.getUuid(), "travel_refund", serverName + "->" + targetServer, fee, Collections.emptyMap());
                return null;
            });
            return new OperationResult(false, color("&cUnable to authorize the server switch."));
        }
        if (!writeSession(snapshot, true)) {
            clearTravelTicket(player.getUniqueId());
            unfreezeMutationAuthority(player.getUniqueId());
            withProfile(player, profile -> {
                profile.addGold(fee);
                appendLedgerMutation(profile.getUuid(), "travel_refund", serverName + "->" + targetServer, fee, Collections.emptyMap());
                return null;
            });
            return new OperationResult(false, color("&cLive routing state unavailable. Travel aborted."));
        }
        if (!sendProxyConnect(player, targetServer, transferId, expectedProfileVersion, expectedGuildName, expectedGuildVersion)) {
            clearTravelTicket(player.getUniqueId());
            unfreezeMutationAuthority(player.getUniqueId());
            withProfile(player, profile -> {
                profile.addGold(fee);
                appendLedgerMutation(profile.getUuid(), "travel_refund", serverName + "->" + targetServer, fee, Collections.emptyMap());
                return null;
            });
            return new OperationResult(false, color("&cProxy routing rejected the request."));
        }
        verifyTravelRouting(player.getUniqueId(), player.getName(), targetServer, fee);
        writeAudit("travel", player.getUniqueId() + ":" + serverName + "->" + targetServer + ":fee=" + fee);
        return new OperationResult(true, color("&aTraveling to &e" + targetServer));
    }

    public OperationResult adminGrantItem(CommandSender sender, Player target, String itemId, int amount) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Admin item grants paused."));
        }
        if (amount <= 0 || !items.contains("materials." + itemId.toLowerCase(Locale.ROOT))) {
            return new OperationResult(false, color("&cInvalid admin item grant."));
        }
        withProfile(target, profile -> {
            profile.addItem(itemId, amount);
            appendLedgerMutation(profile.getUuid(), "admin_reward_grant", "item:" + itemId, 0.0D, Map.of(itemId.toLowerCase(Locale.ROOT), amount));
            syncCollectQuestProgress(profile);
            return null;
        });
        writeAudit("admin_item", sender.getName() + ":" + target.getUniqueId() + ":" + itemId + ":" + amount);
        return new OperationResult(true, color("&aGranted &e" + itemId + " x" + amount + " &7to &e" + target.getName()));
    }

    public OperationResult adminAdjustGold(CommandSender sender, Player target, double delta) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Admin gold changes paused."));
        }
        withProfile(target, profile -> {
            if (delta >= 0.0D) {
                profile.addGold(delta);
            } else {
                profile.spendGold(-delta);
            }
            appendLedgerMutation(profile.getUuid(), "admin_reward_grant", "gold", delta, Collections.emptyMap());
            return null;
        });
        writeAudit("admin_gold", sender.getName() + ":" + target.getUniqueId() + ":" + delta);
        return new OperationResult(true, color("&aAdjusted gold for &e" + target.getName() + " &7delta=&e" + money(delta)));
    }

    public OperationResult createGuild(Player player, String requestedName) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Guild changes paused."));
        }
        String guildName = normalizeGuild(requestedName);
        if (guildName.isBlank() || guildName.length() > 16) {
            return new OperationResult(false, color("&cGuild name must be 1-16 lowercase characters."));
        }
        return withProfile(player, profile -> {
            if (!profile.getGuildName().isBlank()) {
                return new OperationResult(false, color("&eAlready in guild &6" + profile.getGuildName()));
            }
            if (getGuild(guildName).isPresent()) {
                return new OperationResult(false, color("&cGuild already exists."));
            }
            RpgGuild guild = new RpgGuild(guildName, player.getUniqueId().toString());
            guilds.put(guildName, guild);
            dirtyGuilds.add(guildName);
            profile.setGuildName(guildName);
            writeSession(profile, true);
            writeAudit("guild_create", player.getUniqueId() + ":" + guildName);
            return new OperationResult(true, color("&aCreated guild &e" + guildName));
        });
    }

    public OperationResult inviteGuild(Player inviter, Player target) {
        return withProfile(inviter, inviterProfile -> {
            if (inviterProfile.getGuildName().isBlank()) {
                return new OperationResult(false, color("&cYou are not in a guild."));
            }
            String guildName = inviterProfile.getGuildName();
            String guildKey = normalizeGuild(guildName);
            synchronized (guildLocks.computeIfAbsent(guildKey, ignored -> new Object())) {
                Optional<RpgGuild> guildOptional = getGuild(guildName);
                if (guildOptional.isEmpty()) {
                    return new OperationResult(false, color("&cGuild data missing."));
                }
                RpgGuild guild = guildOptional.get();
                if (!guild.getOwnerUuid().equals(inviter.getUniqueId().toString())) {
                    return new OperationResult(false, color("&cOnly the guild owner can invite players."));
                }
                guild.invite(target.getUniqueId().toString(), System.currentTimeMillis() + 600_000L);
                dirtyGuilds.add(guildKey);
                writeAudit("guild_invite", inviter.getUniqueId() + ":" + target.getUniqueId() + ":" + guildName);
                return new OperationResult(true, color("&aInvited &e" + target.getName() + " &7to guild &e" + guildName));
            }
        });
    }

    public OperationResult joinGuild(Player player, String requestedName) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Guild changes paused."));
        }
        String guildName = normalizeGuild(requestedName);
        return withProfile(player, profile -> {
            if (!profile.getGuildName().isBlank()) {
                return new OperationResult(false, color("&eAlready in guild &6" + profile.getGuildName()));
            }
            String guildKey = normalizeGuild(guildName);
            synchronized (guildLocks.computeIfAbsent(guildKey, ignored -> new Object())) {
                Optional<RpgGuild> guildOptional = getGuild(guildName);
                if (guildOptional.isEmpty()) {
                    return new OperationResult(false, color("&cGuild not found."));
                }
                RpgGuild guild = guildOptional.get();
                guild.purgeExpiredInvites();
                if (!guild.hasInvite(player.getUniqueId().toString())) {
                    return new OperationResult(false, color("&cNo active invite for guild &6" + guildName));
                }
                guild.addMember(player.getUniqueId().toString());
                dirtyGuilds.add(guildKey);
                profile.setGuildName(guildName);
                writeSession(profile, true);
                writeAudit("guild_join", player.getUniqueId() + ":" + guildName);
                return new OperationResult(true, color("&aJoined guild &e" + guildName));
            }
        });
    }

    public OperationResult leaveGuild(Player player) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Guild changes paused."));
        }
        return withProfile(player, profile -> {
            String guildName = profile.getGuildName();
            if (guildName.isBlank()) {
                return new OperationResult(false, color("&eYou are not in a guild."));
            }
            String guildKey = normalizeGuild(guildName);
            synchronized (guildLocks.computeIfAbsent(guildKey, ignored -> new Object())) {
                Optional<RpgGuild> guildOptional = getGuild(guildName);
                if (guildOptional.isEmpty()) {
                    profile.setGuildName("");
                    return new OperationResult(true, color("&eDetached from missing guild state."));
                }
                RpgGuild guild = guildOptional.get();
                String playerUuid = player.getUniqueId().toString();
                if (guild.getOwnerUuid().equals(playerUuid) && guild.getMembersView().size() > 1) {
                    return new OperationResult(false, color("&cOwner cannot leave while other members remain."));
                }
                guild.removeMember(playerUuid);
                if (guild.getMembersView().isEmpty()) {
                    guilds.remove(guildKey);
                    dirtyGuilds.remove(guildKey);
                    if (!deleteGuildFromMySql(guildName) && mysqlAuthorityRequired()) {
                        guilds.put(guildKey, guild);
                        dirtyGuilds.add(guildKey);
                        return new OperationResult(false, color("&cGuild authority unavailable. Leave aborted."));
                    }
                    try {
                        Files.deleteIfExists(guildPath(guildName));
                    } catch (IOException exception) {
                        plugin.getLogger().warning("Unable to delete guild file: " + exception.getMessage());
                    }
                } else {
                    dirtyGuilds.add(guildKey);
                }
                profile.setGuildName("");
                writeSession(profile, true);
                writeAudit("guild_leave", playerUuid + ":" + guildName);
                return new OperationResult(true, color("&eLeft guild &6" + guildName));
            }
        });
    }

    public OperationResult depositGuildGold(Player player, double amount) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Guild bank changes paused."));
        }
        if (amount <= 0.0D) {
            return new OperationResult(false, color("&cAmount must be positive."));
        }
        return withProfile(player, profile -> {
            if (profile.getGuildName().isBlank()) {
                return new OperationResult(false, color("&cYou are not in a guild."));
            }
            String guildKey = normalizeGuild(profile.getGuildName());
            synchronized (guildLocks.computeIfAbsent(guildKey, ignored -> new Object())) {
                Optional<RpgGuild> guildOptional = getGuild(profile.getGuildName());
                if (guildOptional.isEmpty()) {
                    return new OperationResult(false, color("&cGuild data missing."));
                }
                if (!profile.spendGold(amount)) {
                    return new OperationResult(false, color("&cNeed " + money(amount) + " gold."));
                }
                RpgGuild guild = guildOptional.get();
                guild.addBankGold(amount);
                dirtyGuilds.add(guildKey);
                appendLedgerMutation(profile.getUuid(), "guild_bank_deposit_gold", guild.getName(), -amount, Collections.emptyMap());
                writeAudit("guild_gold", player.getUniqueId() + ":" + guild.getName() + ":" + amount);
                return new OperationResult(true, color("&aDeposited &e" + money(amount) + " &7to guild bank."));
            }
        });
    }

    public OperationResult depositGuildItem(Player player, String itemId, int amount) {
        if (safeMode) {
            return new OperationResult(false, color("&cBackend safe mode active. Guild bank changes paused."));
        }
        if (amount <= 0) {
            return new OperationResult(false, color("&cAmount must be positive."));
        }
        return withProfile(player, profile -> {
            if (profile.getGuildName().isBlank()) {
                return new OperationResult(false, color("&cYou are not in a guild."));
            }
            if (isBoundMaterial(itemId)) {
                return new OperationResult(false, color("&cBound items cannot be pooled through guild storage."));
            }
            String guildKey = normalizeGuild(profile.getGuildName());
            synchronized (guildLocks.computeIfAbsent(guildKey, ignored -> new Object())) {
                Optional<RpgGuild> guildOptional = getGuild(profile.getGuildName());
                if (guildOptional.isEmpty()) {
                    return new OperationResult(false, color("&cGuild data missing."));
                }
                if (!profile.removeItem(itemId, amount)) {
                    return new OperationResult(false, color("&cNot enough items."));
                }
                RpgGuild guild = guildOptional.get();
                guild.addBankItem(itemId, amount);
                dirtyGuilds.add(guildKey);
                appendLedgerMutation(profile.getUuid(), "guild_bank_deposit_item", guild.getName(), 0.0D, Map.of(itemId.toLowerCase(Locale.ROOT), -amount));
                syncCollectQuestProgress(profile);
                writeAudit("guild_item", player.getUniqueId() + ":" + guild.getName() + ":" + itemId + ":" + amount);
                return new OperationResult(true, color("&aDeposited &e" + itemId + " x" + amount + " &7to guild bank."));
            }
        });
    }

    public String guildSummary(Player player) {
        return withProfile(player, profile -> {
            if (profile.getGuildName().isBlank()) {
                return color("&eYou are not in a guild.");
            }
            String guildKey = normalizeGuild(profile.getGuildName());
            synchronized (guildLocks.computeIfAbsent(guildKey, ignored -> new Object())) {
                Optional<RpgGuild> guildOptional = getGuild(profile.getGuildName());
                if (guildOptional.isEmpty()) {
                    return color("&cGuild state missing.");
                }
                RpgGuild guild = guildOptional.get();
                return color("&6Guild &7name=&e" + guild.getName()
                    + " &7owner=&e" + guild.getOwnerUuid()
                    + " &7members=&e" + guild.getMembersView().size()
                    + " &7bank=&e" + String.join(", ", guild.bankSummary(6)));
            }
        });
    }

    public void applyPassiveStats(Player player) {
        RpgProfile profile = profileSnapshot(player);
        int combat = skillLevel(profile, "combat");
        double maxHealthBonus = Math.min(10.0D, combat * 0.10D);
        Attribute attribute = Attribute.GENERIC_MAX_HEALTH;
        if (player.getAttribute(attribute) != null) {
            player.getAttribute(attribute).setBaseValue(20.0D + maxHealthBonus);
            if (player.getHealth() > 20.0D + maxHealthBonus) {
                player.setHealth(20.0D + maxHealthBonus);
            }
        }
        if (skillLevel(profile, "exploration") >= 10) {
            player.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 20 * 60 * 5, 0, true, false, false));
        }
    }

    public void applyOutgoingDamage(Player player, EntityDamageByEntityEvent event) {
        RpgProfile profile = profileSnapshot(player);
        double gearBonus = totalGearBonus(profile);
        int combat = skillLevel(profile, "combat");
        double bonus = gearBonus * 0.25D + combat * 0.03D;
        event.setDamage(event.getDamage() + bonus);
    }

    public void applyIncomingDamage(Player player, EntityDamageEvent event) {
        RpgProfile profile = profileSnapshot(player);
        double reduction = Math.min(0.25D, totalGearBonus(profile) * 0.02D);
        event.setDamage(event.getDamage() * (1.0D - reduction));
    }

    public String resolveMobId(Entity entity) {
        String tag = tagValue(entity, "rpg_mob:");
        if (tag != null) {
            return tag;
        }
        String normalizedName = normalize(entity.customName() != null ? plain(entity.customName()) : entity.getName());
        for (String mobId : keys(mobs)) {
            if (mobId.equals(normalizedName)) {
                return mobId;
            }
        }
        return switch (entity.getType()) {
            case PILLAGER, ZOMBIE, HUSK -> mobs.contains("goblin") ? "goblin" : null;
            case WOLF -> mobs.contains("forest_wolf") ? "forest_wolf" : null;
            case WITCH, EVOKER -> mobs.contains("cave_shaman") ? "cave_shaman" : null;
            default -> null;
        };
    }

    public String resolveBossId(Entity entity) {
        String tag = tagValue(entity, "rpg_boss:");
        if (tag != null) {
            return tag;
        }
        String normalizedName = normalize(entity.customName() != null ? plain(entity.customName()) : entity.getName());
        for (String bossId : keys(bosses)) {
            if (bossId.equals(normalizedName)) {
                return bossId;
            }
        }
        return null;
    }

    public LivingEntity spawnConfiguredMob(Location origin, Player owner, String mobId, String dungeonId, String eventId) {
        return spawnConfiguredMob(origin, owner, mobId, dungeonId, eventId, null);
    }

    public LivingEntity spawnConfiguredMob(Location origin, Player owner, String mobId, String dungeonId, String eventId, String instanceId) {
        ConfigurationSection section = mobs.getConfigurationSection(mobId);
        if (section == null || origin.getWorld() == null) {
            return null;
        }
        String category = entityCategory(false, dungeonId, eventId);
        if (!canSpawnRpgEntity(category)) {
            return null;
        }
        EntityType type = switch (mobId) {
            case "goblin" -> EntityType.PILLAGER;
            case "forest_wolf" -> EntityType.WOLF;
            case "cave_shaman" -> EntityType.WITCH;
            default -> EntityType.ZOMBIE;
        };
        Location spawnLoc = origin.clone().add(randomOffset(6.0D), 0.0D, randomOffset(6.0D));
        Entity spawned = origin.getWorld().spawnEntity(spawnLoc, type);
        if (!(spawned instanceof LivingEntity living)) {
            spawned.remove();
            return null;
        }
        configureLivingEntity(living, mobId.replace('_', ' '), section.getDouble("health", 20.0D), section.getDouble("damage", 3.0D));
        living.addScoreboardTag("rpg_mob:" + mobId);
        tagManagedEntity(living, category, owner, dungeonId, eventId, instanceId, entityTtlMillis(category));
        return living;
    }

    public LivingEntity spawnConfiguredBoss(Location origin, String bossId, Player owner, String dungeonId) {
        return spawnConfiguredBoss(origin, bossId, owner, dungeonId, null);
    }

    public LivingEntity spawnConfiguredBoss(Location origin, String bossId, Player owner, String dungeonId, String instanceId) {
        ConfigurationSection section = bosses.getConfigurationSection(bossId);
        if (section == null || origin.getWorld() == null) {
            return null;
        }
        String category = entityCategory(true, dungeonId, null);
        if (!canSpawnRpgEntity(category)) {
            return null;
        }
        EntityType type = switch (bossId) {
            case "goblin_king" -> EntityType.PILLAGER;
            case "forest_guardian" -> EntityType.IRON_GOLEM;
            default -> EntityType.ZOMBIE;
        };
        Entity spawned = origin.getWorld().spawnEntity(origin, type);
        if (!(spawned instanceof LivingEntity living)) {
            spawned.remove();
            return null;
        }
        configureLivingEntity(living, bossId.replace('_', ' '), section.getDouble("health", 200.0D), 8.0D);
        living.addScoreboardTag("rpg_boss:" + bossId);
        tagManagedEntity(living, category, owner, null, null, instanceId, entityTtlMillis(category));
        if (dungeonId != null && !dungeonId.isBlank()) {
            living.addScoreboardTag("rpg_dungeon_boss:" + dungeonId);
        }
        startBossAbilityLoop(living, bossId);
        return living;
    }

    private void startBossAbilityLoop(LivingEntity boss, String bossId) {
        String key = boss.getUniqueId().toString();
        BukkitTask existing = bossTasks.remove(key);
        if (existing != null) {
            existing.cancel();
        }
        BukkitTask task = Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            if (!boss.isValid() || boss.isDead()) {
                BukkitTask removed = bossTasks.remove(key);
                if (removed != null) {
                    removed.cancel();
                }
                return;
            }
            List<String> abilities = bosses.getStringList(bossId + ".abilities");
            if (abilities.isEmpty()) {
                return;
            }
            String ability = abilities.get(ThreadLocalRandom.current().nextInt(abilities.size()));
            List<Player> nearby = boss.getLocation().getNearbyPlayers(12.0D).stream().sorted(Comparator.comparingDouble(p -> p.getLocation().distanceSquared(boss.getLocation()))).toList();
            if (nearby.isEmpty()) {
                return;
            }
            Player target = nearby.getFirst();
            switch (ability) {
                case "smash", "slam" -> {
                    for (Player player : nearby) {
                        player.damage(6.0D, boss);
                        Vector knockback = player.getLocation().toVector().subtract(boss.getLocation().toVector()).normalize().multiply(0.7D);
                        player.setVelocity(knockback.setY(0.25D));
                    }
                    boss.getWorld().strikeLightningEffect(boss.getLocation());
                }
                case "leap" -> {
                    Vector leap = target.getLocation().toVector().subtract(boss.getLocation().toVector()).normalize().multiply(0.8D);
                    leap.setY(0.45D);
                    boss.setVelocity(leap);
                }
                case "summon_minions" -> {
                    int cap = scaling.getInt("mitigations.boss_phase_minion_cap", 12);
                    long current = boss.getWorld().getNearbyEntities(boss.getLocation(), 16.0D, 16.0D, 16.0D).stream()
                        .filter(entity -> tagValue(entity, "rpg_boss_minion:") != null)
                        .count();
                    if (current < cap) {
                        String minionMob = bossId.equals("forest_guardian") ? "forest_wolf" : "goblin";
                        Player reservedOwner = ownerPlayerForEntity(boss);
                        LivingEntity minion = spawnConfiguredMob(boss.getLocation(), reservedOwner == null ? target : reservedOwner, minionMob, null, null);
                        if (minion != null) {
                            minion.addScoreboardTag("rpg_boss_minion:" + bossId);
                        }
                    }
                }
                case "root_snare" -> target.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 5, 1, true, false, true));
                default -> {
                }
            }
        }, 40L, 60L);
        bossTasks.put(key, task);
    }

    public void awardSkillXp(RpgProfile profile, String skillId, String sourceKey) {
        profile.addSkillXp(skillId, skills.getDouble(skillId + ".xp_sources." + sourceKey, 0.0D));
    }

    public void addFlatSkillXp(RpgProfile profile, String skillId, double amount) {
        profile.addSkillXp(skillId, amount);
    }

    public int skillLevel(RpgProfile profile, String skillId) {
        int cap = skills.getInt(skillId + ".levels", 1);
        double xp = profile.getSkillXp(skillId);
        int level = (int) Math.floor(Math.sqrt(xp / 25.0D)) + 1;
        return Math.max(1, Math.min(cap, level));
    }

    public double totalGearBonus(RpgProfile profile) {
        double total = 0.0D;
        for (Map.Entry<String, String> entry : profile.getGearTiersView().entrySet()) {
            total += items.getDouble("tiers." + entry.getValue() + ".stat_bonus", 0.0D);
        }
        return total;
    }

    private void applyQuestRewardXp(RpgProfile profile, String objective, int rewardXp) {
        if (rewardXp <= 0) {
            return;
        }
        switch (objective) {
            case "dungeon_clear" -> {
                addFlatSkillXp(profile, "combat", rewardXp * 0.6D);
                addFlatSkillXp(profile, "exploration", rewardXp * 0.4D);
            }
            case "collect" -> {
                addFlatSkillXp(profile, "crafting", rewardXp * 0.7D);
                addFlatSkillXp(profile, "exploration", rewardXp * 0.3D);
            }
            case "boss_kill" -> addFlatSkillXp(profile, "combat", rewardXp);
            default -> addFlatSkillXp(profile, "combat", rewardXp * 0.75D);
        }
    }

    private void updateQuestProgressForKill(RpgProfile profile, String mobId, boolean bossKill, String bossId) {
        for (String questId : new ArrayList<>(profile.getAcceptedQuestsView())) {
            String objective = quests.getString(questId + ".objective", "kill");
            if ("kill".equals(objective) && mobId.equals(quests.getString(questId + ".mob", ""))) {
                profile.setQuestProgress(questId, Math.min(quests.getInt(questId + ".amount", 1), profile.getQuestProgress(questId) + 1));
            }
            if (bossKill && "boss_kill".equals(objective) && bossId.equals(quests.getString(questId + ".boss", ""))) {
                profile.setQuestProgress(questId, Math.min(quests.getInt(questId + ".amount", 1), profile.getQuestProgress(questId) + 1));
            }
        }
    }

    private void updateQuestProgressForDungeonClear(RpgProfile profile, String dungeonId) {
        for (String questId : new ArrayList<>(profile.getAcceptedQuestsView())) {
            String objective = quests.getString(questId + ".objective", "kill");
            if ("dungeon_clear".equals(objective) && dungeonId.equals(quests.getString(questId + ".dungeon", ""))) {
                profile.setQuestProgress(questId, Math.min(quests.getInt(questId + ".amount", 1), profile.getQuestProgress(questId) + 1));
            }
        }
    }

    public void syncCollectQuestProgress(RpgProfile profile) {
        for (String questId : new ArrayList<>(profile.getAcceptedQuestsView())) {
            String objective = quests.getString(questId + ".objective", "kill");
            if (!"collect".equals(objective)) {
                continue;
            }
            String itemId = quests.getString(questId + ".item", "");
            int target = quests.getInt(questId + ".amount", 1);
            profile.setQuestProgress(questId, Math.min(target, profile.getItemCount(itemId)));
        }
    }

    public String questStatusLine(RpgProfile profile, String questId) {
        int progress = profile.getQuestProgress(questId);
        int amount = quests.getInt(questId + ".amount", 1);
        boolean repeatable = quests.getBoolean(questId + ".repeatable", false);
        String status;
        if (profile.isQuestAccepted(questId)) {
            status = "accepted " + progress + "/" + amount;
        } else if (!repeatable && profile.isQuestCompleted(questId)) {
            status = "completed";
        } else if (profile.getQuestCooldown(questId) > System.currentTimeMillis()) {
            status = "cooldown " + secondsRemaining(profile.getQuestCooldown(questId)) + "s";
        } else {
            status = "available";
        }
        return color("&6" + questId + " &7(" + status + ")");
    }

    private int spawnDungeonWave(Location origin, Player owner, String dungeonId, String instanceId) {
        List<String> trash = dungeons.getStringList(dungeonId + ".trash_mobs");
        int count = Math.max(6, trash.size() * 3);
        int spawned = 0;
        for (int index = 0; index < count; index++) {
            String mobId = trash.get(index % trash.size());
            if (spawnConfiguredMob(origin, owner, mobId, dungeonId, null, instanceId) != null) {
                spawned += 1;
            }
        }
        return spawned;
    }

    private void autoAcceptStarterQuest(RpgProfile profile) {
        if (!quests.contains("starter_hunt")) {
            return;
        }
        if (!profile.isQuestAccepted("starter_hunt") && !profile.isQuestCompleted("starter_hunt")) {
            profile.acceptQuest("starter_hunt");
        }
    }

    private Map<String, Integer> rollConfiguredDrops(ConfigurationSection section) {
        Map<String, Integer> rolled = new LinkedHashMap<>();
        if (section == null) {
            return rolled;
        }
        for (String key : section.getKeys(false)) {
            double configured = section.getDouble(key, 0.0D);
            int guaranteed = (int) Math.floor(configured);
            double fractional = configured - guaranteed;
            int total = guaranteed;
            if (fractional > 0.0D && ThreadLocalRandom.current().nextDouble() < fractional) {
                total += 1;
            }
            if (total > 0) {
                rolled.put(key, total);
            }
        }
        return rolled;
    }

    private Map<String, Integer> rollRareBossDrops(ConfigurationSection section) {
        Map<String, Integer> rolled = new LinkedHashMap<>();
        if (section == null) {
            return rolled;
        }
        for (String key : section.getKeys(false)) {
            int configuredAmount = section.getInt(key, 0);
            if (configuredAmount <= 0) {
                continue;
            }
            if (ThreadLocalRandom.current().nextDouble() < 0.25D) {
                rolled.put(key, configuredAmount);
            }
        }
        return rolled;
    }

    private double configuredMobGold(String mobId) {
        if (economy.contains("faucets.mobs." + mobId)) {
            return economy.getDouble("faucets.mobs." + mobId, 0.0D);
        }
        return mobs.getDouble(mobId + ".currency_drop", 0.0D);
    }

    private void removeItems(RpgProfile profile, Map<String, Integer> required) {
        for (Map.Entry<String, Integer> entry : required.entrySet()) {
            profile.removeItem(entry.getKey(), entry.getValue());
        }
    }

    private void addItems(RpgProfile profile, Map<String, Integer> itemsToAdd) {
        for (Map.Entry<String, Integer> entry : itemsToAdd.entrySet()) {
            profile.addItem(entry.getKey(), entry.getValue());
        }
    }

    private String missingItems(RpgProfile profile, Map<String, Integer> required) {
        List<String> missing = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : required.entrySet()) {
            int have = profile.getItemCount(entry.getKey());
            if (have < entry.getValue()) {
                missing.add(entry.getKey() + " " + have + "/" + entry.getValue());
            }
        }
        return String.join(", ", missing);
    }

    private long nonceWindowMillis() {
        return persistence.getLong("write_policy.idempotent_transaction_window_seconds", 300L) * 1000L;
    }

    private long claimRetentionMillis() {
        long configuredDays = persistence.getLong("write_policy.transaction_ledger_retention_days", 14L);
        return Math.max(CLAIM_RETENTION_MILLIS, configuredDays * 24L * 60L * 60L * 1000L);
    }

    private ZoneId rewardBoundaryZone() {
        String configuredZone = network.getString("operational.reward_boundary_timezone", DEFAULT_REWARD_ZONE.getId());
        try {
            return ZoneId.of(configuredZone);
        } catch (DateTimeException ignored) {
            return DEFAULT_REWARD_ZONE;
        }
    }

    private String dailyDateKey(long epochMillis) {
        return LocalDate.ofInstant(Instant.ofEpochMilli(epochMillis), rewardBoundaryZone()).toString();
    }

    private String buildSummonOperationKey(UUID playerUuid, String bossId, String dungeonId) {
        return serverName + ":" + playerUuid + ":" + bossId + ":" + (dungeonId == null || dungeonId.isBlank() ? "open" : dungeonId) + ":" + System.currentTimeMillis();
    }

    private String rewardSuffix(Map<String, Integer> itemsGranted) {
        if (itemsGranted.isEmpty()) {
            return "";
        }
        return " &7items=&e" + itemsGranted;
    }

    private Map<String, Integer> intMap(ConfigurationSection section) {
        Map<String, Integer> map = new LinkedHashMap<>();
        if (section == null) {
            return map;
        }
        for (String key : section.getKeys(false)) {
            map.put(key, section.getInt(key, 0));
        }
        return map;
    }

    private List<String> keys(YamlConfiguration configuration) {
        ConfigurationSection rootSection = configuration.getConfigurationSection("");
        if (rootSection == null) {
            return List.of();
        }
        return new ArrayList<>(rootSection.getKeys(false));
    }

    private void configureLivingEntity(LivingEntity entity, String label, double health, double damage) {
        entity.customName(Component.text(ChatColor.translateAlternateColorCodes('&', "&6" + label)));
        entity.setCustomNameVisible(true);
        entity.setRemoveWhenFarAway(false);
        if (entity.getAttribute(Attribute.GENERIC_MAX_HEALTH) != null) {
            entity.getAttribute(Attribute.GENERIC_MAX_HEALTH).setBaseValue(health);
            entity.setHealth(Math.min(health, entity.getHealth()));
            entity.setHealth(health);
        }
        if (entity.getAttribute(Attribute.GENERIC_ATTACK_DAMAGE) != null) {
            entity.getAttribute(Attribute.GENERIC_ATTACK_DAMAGE).setBaseValue(damage);
        }
    }

    private double randomOffset(double radius) {
        return ThreadLocalRandom.current().nextDouble(-radius, radius);
    }

    private String tagValue(Entity entity, String prefix) {
        for (String tag : entity.getScoreboardTags()) {
            if (tag.startsWith(prefix)) {
                return tag.substring(prefix.length());
            }
        }
        return null;
    }

    private String normalizeGuild(String requestedName) {
        return normalize(requestedName).replaceAll("[^a-z0-9_-]", "");
    }

    private String normalize(String input) {
        return input == null ? "" : input.toLowerCase(Locale.ROOT).replace(' ', '_');
    }

    private String plain(Component component) {
        return component == null ? "" : component.toString();
    }

    private String color(String text) {
        return ChatColor.translateAlternateColorCodes('&', text);
    }

    private String money(double amount) {
        return String.format(Locale.US, "%.2f", amount);
    }

    private boolean isMutationFrozen(UUID uuid) {
        return uuid != null && transferFrozenProfiles.contains(uuid);
    }

    private void freezeMutationAuthority(UUID uuid) {
        if (uuid != null) {
            transferFrozenProfiles.add(uuid);
        }
    }

    private void unfreezeMutationAuthority(UUID uuid) {
        if (uuid != null) {
            transferFrozenProfiles.remove(uuid);
        }
    }

    private boolean isTravelAllowed(String targetServer) {
        String targetRole = network.getString("servers." + targetServer + ".role", "");
        if (targetRole.isBlank()) {
            return false;
        }
        String targetAddress = network.getString("servers." + targetServer + ".address", "");
        if (!targetAddress.startsWith("127.0.0.1:")) {
            return false;
        }
        return switch (serverRole.toLowerCase(Locale.ROOT)) {
            case "lobby" -> "progression".equalsIgnoreCase(targetRole);
            case "progression" -> Set.of("lobby", "instance", "boss", "event").contains(targetRole.toLowerCase(Locale.ROOT));
            case "instance", "boss", "event" -> Set.of("progression", "lobby").contains(targetRole.toLowerCase(Locale.ROOT));
            default -> false;
        };
    }

    private long secondsRemaining(long futureMillis) {
        return Math.max(0L, (futureMillis - System.currentTimeMillis() + 999L) / 1000L);
    }

    private boolean authorizeJoin(Player player, LiveSession previousSession) {
        if ("lobby".equalsIgnoreCase(serverRole)) {
            unfreezeMutationAuthority(player.getUniqueId());
            return true;
        }
        if (mysqlAuthorityRequired() && safeMode) {
            player.sendMessage(color("&cAuthoritative persistence unavailable. Routed to maintenance lobby."));
            rerouteUnauthorizedJoin(player, previousSession == null ? "" : previousSession.server());
            return false;
        }
        TravelTicket ticket = consumeTravelTicket(player.getUniqueId(), serverName, previousSession);
        if (ticket != null) {
            if (ticket.transferId().isBlank()) {
                enterSafeMode("Travel barrier transfer id missing");
                rerouteUnauthorizedJoin(player, ticket.sourceServer());
                return false;
            }
            if (ticket.versionClaim() < ticket.expectedProfileVersion()
                || ticket.versionClaim() < ticket.expectedInventoryVersion()
                || ticket.versionClaim() < ticket.expectedEconomyVersion()) {
                enterSafeMode("Travel version claim mismatch");
                rerouteUnauthorizedJoin(player, ticket.sourceServer());
                return false;
            }
            long durableProfileVersion = readProfileDurableVersion(player.getUniqueId());
            if (durableProfileVersion < ticket.expectedProfileVersion()
                || durableProfileVersion < ticket.expectedInventoryVersion()
                || durableProfileVersion < ticket.expectedEconomyVersion()) {
                enterSafeMode("Travel version barrier profile mismatch");
                rerouteUnauthorizedJoin(player, ticket.sourceServer());
                return false;
            }
            if (!ticket.guildName().isBlank() && ticket.expectedGuildVersion() > 0L) {
                long durableGuildVersion = readGuildDurableVersion(ticket.guildName());
                if (durableGuildVersion < ticket.expectedGuildVersion()) {
                    enterSafeMode("Travel version barrier guild mismatch");
                    rerouteUnauthorizedJoin(player, ticket.sourceServer());
                    return false;
                }
            }
            unfreezeMutationAuthority(player.getUniqueId());
            return true;
        }
        if (previousSession != null && serverName.equalsIgnoreCase(previousSession.server())) {
            return true;
        }
        unfreezeMutationAuthority(player.getUniqueId());
        rerouteUnauthorizedJoin(player, previousSession == null ? "" : previousSession.server());
        return false;
    }

    private void rerouteUnauthorizedJoin(Player player, String previousServer) {
        String safeServer = network.getString("operational.maintenance_mode_server", "lobby");
        writeAudit("travel_block", player.getUniqueId() + ":" + previousServer + "->" + serverName);
        if (!safeServer.equalsIgnoreCase(serverName) && sendProxyConnect(player, safeServer, "", 0L, "", 0L)) {
            player.sendMessage(color("&cUnauthorized server switch blocked."));
            return;
        }
        player.kickPlayer(color("&cUnauthorized server switch blocked."));
    }

    private boolean sendProxyConnect(Player player, String targetServer, String transferId, long expectedProfileVersion, String guildName, long expectedGuildVersion) {
        try {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            DataOutputStream output = new DataOutputStream(buffer);
            output.writeUTF("Connect");
            output.writeUTF(targetServer);
            player.sendPluginMessage(plugin, "BungeeCord", buffer.toByteArray());
            writeAudit("travel_handoff", player.getUniqueId() + ":" + serverName + "->" + targetServer + ":transfer=" + transferId
                + ":profile_v=" + expectedProfileVersion + ":guild=" + normalizeGuild(guildName) + ":guild_v=" + expectedGuildVersion);
            return true;
        } catch (IOException | IllegalArgumentException exception) {
            plugin.getLogger().warning("Proxy route failed: " + exception.getMessage());
            return false;
        }
    }

    private void verifyTravelRouting(UUID uuid, String latestName, String targetServer, double fee) {
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            Player localPlayer = Bukkit.getPlayer(uuid);
            if (localPlayer == null) {
                return;
            }
            TravelTicket ticket = loadTravelTicket(uuid);
            if (ticket == null || !targetServer.equalsIgnoreCase(ticket.targetServer())) {
                return;
            }
            unfreezeMutationAuthority(uuid);
            withProfile(uuid, latestName, profile -> {
                profile.addGold(fee);
                appendLedgerMutation(profile.getUuid(), "travel_refund", serverName + "->" + targetServer, fee, Collections.emptyMap());
                clearTravelTicket(uuid);
                localPlayer.sendMessage(color("&cTravel routing failed. Fee refunded."));
                writeAudit("travel_refund", uuid + ":" + serverName + "->" + targetServer + ":fee=" + fee);
                return null;
            });
        }, 60L);
    }

    private LiveSession loadLiveSession(UUID uuid) {
        YamlConfiguration redisYaml = readRedisYamlValue("rpg:session:" + uuid);
        if (redisYaml != null && !redisYaml.getString("server", "").isBlank()) {
            return new LiveSession(
                redisYaml.getString("server", ""),
                redisYaml.getString("role", ""),
                redisYaml.getBoolean("online", false),
                redisYaml.getString("guild", ""),
                redisYaml.getString("active_dungeon", ""),
                redisYaml.getString("active_dungeon_instance", ""),
                redisYaml.getLong("updated_at", 0L)
            );
        }
        if (redisSessionRequired()) {
            return null;
        }
        Path sessionPath = sessionDir.resolve(uuid + ".yml");
        if (!Files.exists(sessionPath)) {
            return null;
        }
        YamlConfiguration yaml = readYaml(sessionPath);
        String server = yaml.getString("server", "");
        if (server.isBlank()) {
            return null;
        }
        return new LiveSession(
            server,
            yaml.getString("role", ""),
            yaml.getBoolean("online", false),
            yaml.getString("guild", ""),
            yaml.getString("active_dungeon", ""),
            yaml.getString("active_dungeon_instance", ""),
            yaml.getLong("updated_at", 0L)
        );
    }

    private boolean issueTravelTicket(UUID uuid, String transferId, String targetServer, long expectedProfileVersion, String guildName, long expectedGuildVersion) {
        long now = System.currentTimeMillis();
        long expiresAt = now + Math.max(15_000L, scaling.getLong("limits.transfer_ticket_seconds", 15L) * 1000L);
        String normalizedGuild = normalizeGuild(guildName);
        String transferLease = sha256(uuid + "|" + transferId + "|" + serverName + "|" + targetServer + "|" + now);
        long inventoryVersion = expectedProfileVersion;
        long economyVersion = expectedProfileVersion;
        long versionClaim = Math.max(expectedProfileVersion, Math.max(expectedGuildVersion, Math.max(inventoryVersion, economyVersion)));
        TravelTicket ticket = new TravelTicket(transferId, transferLease, serverName, targetServer, now, expiresAt,
            expectedProfileVersion, inventoryVersion, economyVersion, normalizedGuild, Math.max(0L, expectedGuildVersion), versionClaim);
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("transfer_id", ticket.transferId());
        yaml.set("transfer_lease", ticket.transferLease());
        yaml.set("source", ticket.sourceServer());
        yaml.set("target", ticket.targetServer());
        yaml.set("issued_at", ticket.issuedAt());
        yaml.set("expires_at", ticket.expiresAt());
        yaml.set("expected_profile_version", ticket.expectedProfileVersion());
        yaml.set("expected_inventory_version", ticket.expectedInventoryVersion());
        yaml.set("expected_economy_version", ticket.expectedEconomyVersion());
        yaml.set("expected_guild", ticket.guildName());
        yaml.set("expected_guild_version", ticket.expectedGuildVersion());
        yaml.set("version_claim", ticket.versionClaim());
        String serialized = yaml.saveToString();
        if (redisSessionRequired()) {
            int ttlSeconds = Math.max(15, (int) ((expiresAt - System.currentTimeMillis() + 999L) / 1000L));
            boolean mirrored = writeRedisYamlValue("rpg:travel:" + uuid, ttlSeconds, serialized);
            if (!mirrored) {
                enterSafeMode("Redis session backend unavailable");
                return false;
            }
        }
        if (persistence.getBoolean("local_fallback.enabled", true)) {
            writeYaml(ticketDir.resolve(uuid + ".yml"), serialized);
        }
        return true;
    }

    private TravelTicket loadTravelTicket(UUID uuid) {
        YamlConfiguration redisYaml = readRedisYamlValue("rpg:travel:" + uuid);
        if (redisYaml != null && !redisYaml.getString("target", "").isBlank()) {
            long expiresAt = redisYaml.getLong("expires_at", 0L);
            if (expiresAt <= System.currentTimeMillis()) {
                clearTravelTicket(uuid);
                return null;
            }
            return new TravelTicket(
                redisYaml.getString("transfer_id", ""),
                redisYaml.getString("transfer_lease", ""),
                redisYaml.getString("source", ""),
                redisYaml.getString("target", ""),
                redisYaml.getLong("issued_at", 0L),
                expiresAt,
                redisYaml.getLong("expected_profile_version", 0L),
                redisYaml.getLong("expected_inventory_version", redisYaml.getLong("expected_profile_version", 0L)),
                redisYaml.getLong("expected_economy_version", redisYaml.getLong("expected_profile_version", 0L)),
                normalizeGuild(redisYaml.getString("expected_guild", "")),
                redisYaml.getLong("expected_guild_version", 0L),
                redisYaml.getLong("version_claim", redisYaml.getLong("expected_profile_version", 0L))
            );
        }
        if (redisSessionRequired()) {
            return null;
        }
        Path path = ticketDir.resolve(uuid + ".yml");
        if (!Files.exists(path)) {
            return null;
        }
        YamlConfiguration yaml = readYaml(path);
        long expiresAt = yaml.getLong("expires_at", 0L);
        if (expiresAt <= System.currentTimeMillis()) {
            clearTravelTicket(uuid);
            return null;
        }
        return new TravelTicket(
            yaml.getString("transfer_id", ""),
            yaml.getString("transfer_lease", ""),
            yaml.getString("source", ""),
            yaml.getString("target", ""),
            yaml.getLong("issued_at", 0L),
            expiresAt,
            yaml.getLong("expected_profile_version", 0L),
            yaml.getLong("expected_inventory_version", yaml.getLong("expected_profile_version", 0L)),
            yaml.getLong("expected_economy_version", yaml.getLong("expected_profile_version", 0L)),
            normalizeGuild(yaml.getString("expected_guild", "")),
            yaml.getLong("expected_guild_version", 0L),
            yaml.getLong("version_claim", yaml.getLong("expected_profile_version", 0L))
        );
    }

    private TravelTicket consumeTravelTicket(UUID uuid, String expectedTarget, LiveSession previousSession) {
        TravelTicket ticket = loadTravelTicket(uuid);
        if (ticket == null || !expectedTarget.equalsIgnoreCase(ticket.targetServer())) {
            return null;
        }
        if (ticket.transferLease().isBlank() || ticket.versionClaim() <= 0L) {
            transferBarrierRejects.incrementAndGet();
            writeAudit("travel_fence_reject", uuid + ":invalid_lease:" + expectedTarget + ":transfer=" + ticket.transferId());
            clearTravelTicket(uuid);
            return null;
        }
        if (previousSession != null && previousSession.updatedAt() > 0L && ticket.issuedAt() > 0L
            && previousSession.updatedAt() > ticket.issuedAt()
            && !ticket.sourceServer().equalsIgnoreCase(previousSession.server())) {
            transferBarrierRejects.incrementAndGet();
            writeAudit("travel_fence_reject", uuid + ":" + previousSession.server() + "->" + expectedTarget + ":transfer=" + ticket.transferId());
            clearTravelTicket(uuid);
            return null;
        }
        clearTravelTicket(uuid);
        return ticket;
    }

    private void clearTravelTicket(UUID uuid) {
        try {
            Files.deleteIfExists(ticketDir.resolve(uuid + ".yml"));
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to clear travel ticket: " + exception.getMessage());
        }
        deleteRedisKey("rpg:travel:" + uuid);
    }

    private long instanceHoldMillis() {
        long configured = scaling.getLong("limits.instance_expiry_seconds", 180L);
        long reconnectFloor = exploit.getLong("progression.reconnect_state_hold_seconds", 30L);
        return Math.max(configured, reconnectFloor) * 1000L;
    }

    private DungeonInstanceState createDungeonInstance(UUID ownerUuid, String dungeonId, Set<UUID> partyMembers) {
        return instanceOrchestrator.allocateDungeonInstance(ownerUuid, dungeonId, partyMembers);
    }

    private void loadPersistedInstances() {
        if (!Files.isDirectory(instanceDir)) {
            return;
        }
        try (var paths = Files.list(instanceDir)) {
            paths.filter(path -> path.getFileName().toString().endsWith(".yml")).forEach(path -> {
                try {
                    DungeonInstanceState instance = DungeonInstanceState.fromYaml(readYaml(path));
                    if (instance == null) {
                        return;
                    }
                    dungeonInstances.put(instance.instanceId, instance);
                    dungeonOwnerInstances.put(instance.ownerUuid, instance.instanceId);
                    dungeonWorldToInstance.put(instance.worldName, instance.instanceId);
                } catch (Exception exception) {
                    plugin.getLogger().warning("Unable to load dungeon instance state " + path + ": " + exception.getMessage());
                }
            });
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to scan dungeon instances: " + exception.getMessage());
        }
    }

    private void persistDungeonInstance(DungeonInstanceState instance) {
        if (instance == null) {
            return;
        }
        dungeonInstances.put(instance.instanceId, instance);
        dungeonOwnerInstances.put(instance.ownerUuid, instance.instanceId);
        dungeonWorldToInstance.put(instance.worldName, instance.instanceId);
        writeYaml(instanceDir.resolve(instance.instanceId + ".yml"), instance.toYaml().saveToString());
    }

    private DungeonInstanceState loadDungeonInstance(String instanceId) {
        if (instanceId == null || instanceId.isBlank()) {
            return null;
        }
        DungeonInstanceState cached = dungeonInstances.get(instanceId);
        if (cached != null) {
            return cached;
        }
        Path path = instanceDir.resolve(instanceId + ".yml");
        if (!Files.exists(path)) {
            return null;
        }
        DungeonInstanceState loaded = DungeonInstanceState.fromYaml(readYaml(path));
        if (loaded != null) {
            dungeonInstances.put(loaded.instanceId, loaded);
            dungeonOwnerInstances.put(loaded.ownerUuid, loaded.instanceId);
            dungeonWorldToInstance.put(loaded.worldName, loaded.instanceId);
        }
        return loaded;
    }

    private World ensureDungeonWorld(DungeonInstanceState instance) {
        if (instance == null) {
            return null;
        }
        World world = Bukkit.getWorld(instance.worldName);
        long nextExpiry = System.currentTimeMillis() + instanceHoldMillis();
        if (world != null) {
            if (instance.expiresAt < nextExpiry - 1000L) {
                instance.extendTo(nextExpiry);
                persistDungeonInstance(instance);
            }
            return world;
        }
        WorldCreator creator = new WorldCreator(instance.worldName);
        creator.type(WorldType.FLAT);
        creator.generateStructures(false);
        world = Bukkit.createWorld(creator);
        if (world != null) {
            world.setAutoSave(false);
            instance.extendTo(nextExpiry);
            persistDungeonInstance(instance);
        }
        return world;
    }

    private Location dungeonEntryLocation(World world) {
        if (world == null) {
            return null;
        }
        int y = Math.max(65, world.getHighestBlockYAt(0, 0) + 1);
        return new Location(world, 0.5D, y, 0.5D);
    }

    private void restoreDungeonInstance(Player player, RpgProfile profile) {
        if (!"instance".equalsIgnoreCase(serverRole) || profile.getActiveDungeon().isBlank() || profile.getActiveDungeonInstanceId().isBlank()) {
            return;
        }
        DungeonInstanceState instance = loadDungeonInstance(profile.getActiveDungeonInstanceId());
        if (instance == null || !player.getUniqueId().equals(instance.ownerUuid) || !profile.getActiveDungeonWorld().equals(instance.worldName)) {
            cleanupOwnedDungeonInstance(player.getUniqueId(), "missing_instance");
            profile.clearActiveDungeon();
            return;
        }
        World world = ensureDungeonWorld(instance);
        if (world == null) {
            cleanupOwnedDungeonInstance(player.getUniqueId(), "world_missing");
            profile.clearActiveDungeon();
            return;
        }
        Location entry = dungeonEntryLocation(world);
        if (entry != null && !player.getWorld().getName().equals(world.getName())) {
            player.teleport(entry);
        }
    }

    public boolean canAccessWorld(Player player, Location target) {
        if (player == null || target == null || target.getWorld() == null) {
            return true;
        }
        return canAccessWorld(player, target.getWorld().getName());
    }

    public boolean canAccessWorld(Player player, String worldName) {
        if (player == null || worldName == null || worldName.isBlank() || !worldName.startsWith("inst_")) {
            return true;
        }
        DungeonInstanceState instance = dungeonInstanceByWorld(worldName);
        return instance != null && instance.isPartyMember(player.getUniqueId());
    }

    public void enforceWorldAccess(Player player) {
        if (player == null || canAccessWorld(player, player.getWorld().getName())) {
            return;
        }
        teleportToPrimaryWorldSpawn(player);
        player.sendMessage(color("&cThis dungeon instance is reserved for another player."));
    }

    private DungeonInstanceState dungeonInstanceByWorld(String worldName) {
        String instanceId = dungeonWorldToInstance.get(worldName);
        if (instanceId != null) {
            return loadDungeonInstance(instanceId);
        }
        for (DungeonInstanceState instance : dungeonInstances.values()) {
            dungeonWorldToInstance.put(instance.worldName, instance.instanceId);
            if (worldName.equals(instance.worldName)) {
                return instance;
            }
        }
        return null;
    }

    private Player ownerPlayerForEntity(Entity entity) {
        String owner = entity == null ? null : tagValue(entity, "rpg_owner:");
        if (owner == null || owner.isBlank()) {
            return null;
        }
        try {
            return Bukkit.getPlayer(UUID.fromString(owner));
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private void holdDungeonInstance(RpgProfile profile) {
        if (profile.getActiveDungeonInstanceId().isBlank()) {
            return;
        }
        DungeonInstanceState instance = loadDungeonInstance(profile.getActiveDungeonInstanceId());
        if (instance == null) {
            return;
        }
        long nextExpiry = System.currentTimeMillis() + instanceHoldMillis();
        if (instance.expiresAt >= nextExpiry - 1000L) {
            return;
        }
        instance.extendTo(nextExpiry);
        persistDungeonInstance(instance);
    }

    private void cleanupOwnedDungeonInstance(UUID ownerUuid, String reason) {
        String instanceId = dungeonOwnerInstances.get(ownerUuid);
        if (instanceId == null) {
            for (DungeonInstanceState instance : dungeonInstances.values()) {
                if (ownerUuid.equals(instance.ownerUuid)) {
                    instanceId = instance.instanceId;
                    break;
                }
            }
        }
        cleanupDungeonInstance(loadDungeonInstance(instanceId), reason);
    }

    private void cleanupDungeonInstance(DungeonInstanceState instance, String reason) {
        if (instance == null) {
            return;
        }
        instanceOrchestrator.markCleanup(instance);
        dungeonInstances.remove(instance.instanceId);
        dungeonOwnerInstances.remove(instance.ownerUuid);
        dungeonWorldToInstance.remove(instance.worldName);
        World world = Bukkit.getWorld(instance.worldName);
        if (world != null) {
            for (Player player : new ArrayList<>(world.getPlayers())) {
                teleportToPrimaryWorldSpawn(player);
            }
            clearWorldEntities(world);
            Bukkit.unloadWorld(world, false);
        }
        deletePathRecursively(Paths.get("").toAbsolutePath().resolve(instance.worldName));
        try {
            Files.deleteIfExists(instanceDir.resolve(instance.instanceId + ".yml"));
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to clear dungeon instance file: " + exception.getMessage());
        }
        instanceOrchestrator.markTerminated(instance);
        writeAudit("dungeon_instance_cleanup", instance.instanceId + ":" + reason);
    }

    private void cleanupExpiredInstances() {
        long now = System.currentTimeMillis();
        long holdMillis = instanceHoldMillis();
        for (DungeonInstanceState instance : new ArrayList<>(dungeonInstances.values())) {
            if (Bukkit.getPlayer(instance.ownerUuid) != null) {
                long nextExpiry = now + holdMillis;
                if (instance.expiresAt < now + (holdMillis / 2L)) {
                    instance.extendTo(nextExpiry);
                    persistDungeonInstance(instance);
                }
                continue;
            }
            if (instance.expired(now)) {
                orphanInstancesCleaned.incrementAndGet();
                cleanupDungeonInstance(instance, "expired");
            }
        }
        cleanupOrphanWorlds();
    }

    private void cleanupOrphanWorlds() {
        for (World world : new ArrayList<>(Bukkit.getWorlds())) {
            String worldName = world.getName();
            if (!worldName.startsWith("inst_")) {
                continue;
            }
            DungeonInstanceState instance = dungeonInstanceByWorld(worldName);
            if (instance != null) {
                continue;
            }
            for (Player player : new ArrayList<>(world.getPlayers())) {
                teleportToPrimaryWorldSpawn(player);
            }
            clearWorldEntities(world);
            Bukkit.unloadWorld(world, false);
            deletePathRecursively(Paths.get("").toAbsolutePath().resolve(worldName));
            orphanInstancesCleaned.incrementAndGet();
            writeAudit("dungeon_instance_cleanup", worldName + ":orphan_world");
        }
    }

    private void teleportToPrimaryWorldSpawn(Player player) {
        World fallback = Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().getFirst();
        if (fallback == null) {
            return;
        }
        Location spawn = fallback.getSpawnLocation().clone().add(0.5D, 0.0D, 0.5D);
        player.teleport(spawn);
    }

    private void clearWorldEntities(World world) {
        if (world == null) {
            return;
        }
        for (Entity entity : new ArrayList<>(world.getEntities())) {
            if (!(entity instanceof Player)) {
                removeManagedEntity(entity);
            }
        }
    }

    public void cleanupEventEntities(String eventId) {
        if (eventId == null || eventId.isBlank()) {
            return;
        }
        for (World world : Bukkit.getWorlds()) {
            for (Entity entity : new ArrayList<>(world.getEntities())) {
                if (entity.getScoreboardTags().contains("rpg_event:" + eventId)) {
                    removeManagedEntity(entity);
                }
            }
        }
    }

    private void rebuildManagedEntityCounters() {
        Map<String, Integer> rebuilt = new LinkedHashMap<>();
        Set<UUID> rebuiltIds = ConcurrentHashMap.newKeySet();
        int total = 0;
        for (World world : Bukkit.getWorlds()) {
            for (Entity entity : world.getEntities()) {
                String category = tagValue(entity, "rpg_category:");
                if (category == null) {
                    continue;
                }
                rebuiltIds.add(entity.getUniqueId());
                total += 1;
                rebuilt.merge("category:" + category.toLowerCase(Locale.ROOT), 1, Integer::sum);
            }
        }
        rebuilt.put("total", total);
        managedEntityIds.clear();
        managedEntityIds.addAll(rebuiltIds);
        managedEntityCounters.clear();
        managedEntityCounters.putAll(rebuilt);
    }

    private void cleanupTaggedEntities() {
        long now = System.currentTimeMillis();
        Map<String, List<Entity>> byCategory = new LinkedHashMap<>();
        Map<UUID, Entity> toRemove = new LinkedHashMap<>();
        for (UUID entityId : new ArrayList<>(managedEntityIds)) {
            Entity entity = Bukkit.getEntity(entityId);
            if (entity == null || !entity.isValid()) {
                managedEntityIds.remove(entityId);
                continue;
            }
            String category = tagValue(entity, "rpg_category:");
            if (category == null) {
                managedEntityIds.remove(entityId);
                continue;
            }
            String expiry = tagValue(entity, "rpg_expires_at:");
            if (expiry != null) {
                try {
                    if (Long.parseLong(expiry) <= now) {
                        toRemove.put(entity.getUniqueId(), entity);
                        continue;
                    }
                } catch (NumberFormatException ignored) {
                    toRemove.put(entity.getUniqueId(), entity);
                    continue;
                }
            }
            String instanceId = tagValue(entity, "rpg_instance:");
            if (instanceId != null) {
                DungeonInstanceState instance = loadDungeonInstance(instanceId);
                World world = entity.getWorld();
                if (instance == null || instance.expired(now) || world == null || !world.getName().equals(instance.worldName)) {
                    toRemove.put(entity.getUniqueId(), entity);
                    continue;
                }
            }
            byCategory.computeIfAbsent(category, ignored -> new ArrayList<>()).add(entity);
        }
        for (Map.Entry<String, List<Entity>> entry : byCategory.entrySet()) {
            List<Entity> entities = entry.getValue();
            int cap = entityCap(entry.getKey());
            if (entities.size() <= cap) {
                continue;
            }
            entities.sort(Comparator.comparingLong(this::entityExpiry));
            for (int index = cap; index < entities.size(); index++) {
                Entity entity = entities.get(index);
                toRemove.put(entity.getUniqueId(), entity);
            }
        }
        toRemove.values().forEach(this::removeManagedEntity);
        trimManagedEntityCounters(byCategory);
    }

    private void markManagedEntityRemoved(Entity entity) {
        if (entity == null) {
            return;
        }
        managedEntityIds.remove(entity.getUniqueId());
        String category = tagValue(entity, "rpg_category:");
        if (category == null) {
            return;
        }
        managedEntityCounters.compute("total", (k, v) -> Math.max(0, (v == null ? 0 : v) - 1));
        managedEntityCounters.compute("category:" + category.toLowerCase(Locale.ROOT), (k, v) -> Math.max(0, (v == null ? 0 : v) - 1));
    }

    private long entityExpiry(Entity entity) {
        String expiry = tagValue(entity, "rpg_expires_at:");
        if (expiry == null || expiry.isBlank()) {
            return Long.MAX_VALUE;
        }
        try {
            return Long.parseLong(expiry);
        } catch (NumberFormatException ignored) {
            return Long.MIN_VALUE;
        }
    }

    private void removeManagedEntity(Entity entity) {
        if (entity == null) {
            return;
        }
        BukkitTask task = bossTasks.remove(entity.getUniqueId().toString());
        if (task != null) {
            task.cancel();
        }
        markManagedEntityRemoved(entity);
        entity.remove();
    }

    private String entityCategory(boolean boss, String dungeonId, String eventId) {
        if (dungeonId != null && !dungeonId.isBlank()) {
            return boss ? "dungeon_bosses" : "dungeon_mobs";
        }
        if (eventId != null && !eventId.isBlank()) {
            return "event_mobs";
        }
        return "boss_mobs";
    }

    private long entityTtlMillis(String category) {
        long fallback = switch (category) {
            case "dungeon_mobs" -> 1800L;
            case "dungeon_bosses" -> 1800L;
            case "event_mobs" -> 900L;
            case "boss_mobs" -> 1800L;
            default -> 600L;
        };
        return Math.max(30L, scaling.getLong("limits.entity_ttl_seconds." + category, fallback)) * 1000L;
    }

    private int entityCap(String category) {
        int fallback = switch (category) {
            case "dungeon_mobs" -> 160;
            case "dungeon_bosses" -> 20;
            case "event_mobs" -> 150;
            case "boss_mobs" -> 40;
            default -> 50;
        };
        return Math.max(1, scaling.getInt("limits.rpg_entity_caps." + category, fallback));
    }

    private boolean canSpawnRpgEntity(String category) {
        int serverCap = scaling.getInt("limits.max_entities_per_server." + serverName, Integer.MAX_VALUE);
        int total = managedEntityCount(null);
        int categoryCount = managedEntityCount(category);
        int categoryCap = entityCap(category);
        double pressure = serverCap <= 0 || serverCap >= Integer.MAX_VALUE / 2 ? 0.0D : (total / (double) Math.max(1, serverCap));
        double hardPressureCap = Math.max(0.05D, Math.min(0.99D, scaling.getDouble("limits.entity_spawn_pressure_hard_cap", 0.95D)));
        if (total >= serverCap || categoryCount >= categoryCap || pressure >= hardPressureCap) {
            managedEntitySpawnDenied.incrementAndGet();
            maybeWarnEntityPressure(category, total, serverCap, categoryCount, categoryCap, pressure);
            return false;
        }
        return true;
    }

    private void maybeWarnEntityPressure(String category, int total, int serverCap, int categoryCount, int categoryCap, double pressure) {
        long now = System.currentTimeMillis();
        long everyMillis = Math.max(15_000L, scaling.getLong("limits.entity_spawn_pressure_warning_seconds", 30L) * 1000L);
        if (now - lastEntityPressureWarningAt < everyMillis) {
            return;
        }
        lastEntityPressureWarningAt = now;
        plugin.getLogger().warning("Entity spawn pressure active category=" + category
            + " total=" + total + "/" + serverCap
            + " category=" + categoryCount + "/" + categoryCap
            + " pressure=" + String.format(Locale.US, "%.3f", pressure));
    }

    private int managedEntityCount(String category) {
        if (category == null || category.isBlank()) {
            return managedEntityCounters.getOrDefault("total", 0);
        }
        return managedEntityCounters.getOrDefault("category:" + category.toLowerCase(Locale.ROOT), 0);
    }

    private void trimManagedEntityCounters(Map<String, List<Entity>> byCategory) {
        int total = 0;
        for (Map.Entry<String, List<Entity>> entry : byCategory.entrySet()) {
            int count = entry.getValue().size();
            total += count;
            managedEntityCounters.put("category:" + entry.getKey().toLowerCase(Locale.ROOT), count);
        }
        managedEntityCounters.put("total", total);
    }

    private void tagManagedEntity(LivingEntity living, String category, Player owner, String dungeonId, String eventId, String instanceId, long ttlMillis) {
        living.addScoreboardTag("rpg_category:" + category);
        living.addScoreboardTag("rpg_expires_at:" + (System.currentTimeMillis() + ttlMillis));
        if (owner != null) {
            living.addScoreboardTag("rpg_owner:" + owner.getUniqueId());
        }
        if (dungeonId != null && !dungeonId.isBlank()) {
            living.addScoreboardTag("rpg_dungeon:" + dungeonId);
        }
        if (eventId != null && !eventId.isBlank()) {
            living.addScoreboardTag("rpg_event:" + eventId);
        }
        if (instanceId != null && !instanceId.isBlank()) {
            living.addScoreboardTag("rpg_instance:" + instanceId);
        }
        managedEntityIds.add(living.getUniqueId());
        managedEntityCounters.merge("total", 1, Integer::sum);
        managedEntityCounters.merge("category:" + category.toLowerCase(Locale.ROOT), 1, Integer::sum);
    }

    public boolean canClaimReservedEntityKill(Player killer, Entity entity) {
        return canClaimReservedEntityKill(killer, entity, false);
    }

    private boolean canClaimReservedEntityKill(Player killer, Entity entity, boolean ignoreInstance) {
        if (killer == null || entity == null) {
            return false;
        }
        String owner = tagValue(entity, "rpg_owner:");
        if (owner != null && !owner.equalsIgnoreCase(killer.getUniqueId().toString())) {
            return false;
        }
        if (ignoreInstance) {
            return true;
        }
        String instanceId = tagValue(entity, "rpg_instance:");
        if (instanceId == null) {
            return true;
        }
        DungeonInstanceState instance = loadDungeonInstance(instanceId);
        return instance != null
            && instance.isPartyMember(killer.getUniqueId())
            && entity.getWorld() != null
            && instance.worldName.equals(entity.getWorld().getName());
    }

    private boolean isBoundMaterial(String itemId) {
        String key = itemId == null ? "" : itemId.toLowerCase(Locale.ROOT);
        return items.getBoolean("materials." + key + ".bound", false);
    }

    private long resolveGuildVersion(String guildName) {
        String key = normalizeGuild(guildName);
        if (key.isBlank()) {
            return 0L;
        }
        synchronized (guildLocks.computeIfAbsent(key, ignored -> new Object())) {
            RpgGuild guild = guilds.computeIfAbsent(key, ignored -> loadGuild(key));
            return guild.getUpdatedAt();
        }
    }

    private boolean commitDurabilityBoundary(UUID playerUuid, long expectedProfileVersion, String expectedGuildName, long expectedGuildVersion) {
        flushPlayer(playerUuid);
        if (expectedGuildName != null && !expectedGuildName.isBlank() && expectedGuildVersion > 0L) {
            flushGuild(expectedGuildName);
        }
        flushLedger();
        boolean profileCommitted = lastFlushedProfileVersion.getOrDefault(playerUuid, 0L) >= expectedProfileVersion;
        boolean guildCommitted = true;
        if (expectedGuildName != null && !expectedGuildName.isBlank() && expectedGuildVersion > 0L) {
            guildCommitted = lastFlushedGuildVersion.getOrDefault(normalizeGuild(expectedGuildName), 0L) >= expectedGuildVersion;
        }
        boolean ledgerCommitted = ledgerQueue.isEmpty();
        if (!profileCommitted || !guildCommitted || !ledgerCommitted) {
            enterSafeMode("Durability boundary violation");
            return false;
        }
        return true;
    }

    public void appendLedgerMutation(UUID playerUuid, String category, String reference, double goldDelta, Map<String, Integer> itemDelta) {
        if (playerUuid == null || category == null || category.isBlank()) {
            return;
        }
        long now = System.currentTimeMillis();
        long operationNumericId = nextLedgerOperationNumericId(now);
        long sequence = operationNumericId;
        Map<String, Integer> copy = new LinkedHashMap<>();
        if (itemDelta != null) {
            for (Map.Entry<String, Integer> entry : itemDelta.entrySet()) {
                if (entry.getValue() != null && entry.getValue() != 0) {
                    copy.put(entry.getKey(), entry.getValue());
                }
            }
        }
        long previousHash = ledgerHashChain.get();
        String normalizedReference = reference == null ? "" : reference;
        long hash = Objects.hash(operationNumericId, now, serverName, playerUuid.toString(), category, normalizedReference, goldDelta, copy, previousHash);
        String operationId = Long.toUnsignedString(operationNumericId);
        String payloadWithoutHash = ledgerPayload(new LedgerPayloadSnapshot(operationId, sequence, now, serverName, playerUuid, category, normalizedReference, goldDelta, copy, previousHash, hash, ""));
        String payloadHash = sha256(payloadWithoutHash);
        String payload = ledgerPayload(new LedgerPayloadSnapshot(operationId, sequence, now, serverName, playerUuid, category, normalizedReference, goldDelta, copy, previousHash, hash, payloadHash));
        LedgerEntry entry = new LedgerEntry(operationId, serverName, sequence, now, playerUuid, category, normalizedReference, goldDelta, copy, payload, payloadHash);
        persistPendingLedgerEntry(entry);
        ledgerQueue.add(entry);
        ledgerHashChain.set(hash);
        int immediateFlushThreshold = Math.max(16, persistence.getInt("write_policy.ledger_immediate_flush_queue_threshold", 64));
        if (requiresImmediateLedgerDurability(category) || ledgerQueue.size() >= immediateFlushThreshold) {
            flushLedger();
        }
    }

    private boolean requiresImmediateLedgerDurability(String category) {
        if (category == null || category.isBlank()) {
            return false;
        }
        List<String> categories = persistence.getStringList("write_policy.ledger_immediate_flush_categories");
        if (!categories.isEmpty()) {
            for (String configured : categories) {
                if (category.equalsIgnoreCase(configured)) {
                    return true;
                }
            }
            return false;
        }
        return category.startsWith("travel_")
            || category.startsWith("boss_summon")
            || category.startsWith("guild_bank_")
            || category.startsWith("dungeon_complete")
            || category.startsWith("event_bonus_reward")
            || category.startsWith("admin_reward");
    }

    private String ledgerPayload(LedgerPayloadSnapshot snapshot) {
        StringJoiner itemJoiner = new StringJoiner(",");
        for (Map.Entry<String, Integer> item : snapshot.itemDelta().entrySet()) {
            itemJoiner.add(item.getKey() + ":" + item.getValue());
        }
        return "operation_id=" + snapshot.operationId() + "\n"
            + "sequence=" + snapshot.sequence() + "\n"
            + "created_at=" + snapshot.createdAt() + "\n"
            + "server=" + snapshot.server() + "\n"
            + "player=" + snapshot.playerUuid() + "\n"
            + "category=" + snapshot.category() + "\n"
            + "reference=" + snapshot.reference() + "\n"
            + "gold_delta=" + snapshot.goldDelta() + "\n"
            + "items=" + itemJoiner + "\n"
            + "previous_hash=" + snapshot.previousHash() + "\n"
            + "entry_hash=" + snapshot.entryHash() + "\n"
            + "payload_hash=" + snapshot.payloadHash() + "\n";
    }

    private Map<String, Integer> parseLedgerItems(String rawItems) {
        Map<String, Integer> items = new LinkedHashMap<>();
        if (rawItems == null || rawItems.isBlank()) {
            return items;
        }
        for (String token : rawItems.split(",")) {
            if (token == null || token.isBlank()) {
                continue;
            }
            String[] parts = token.split(":", 2);
            if (parts.length != 2 || parts[0].isBlank()) {
                continue;
            }
            try {
                items.put(parts[0], Integer.parseInt(parts[1]));
            } catch (NumberFormatException ignored) {
            }
        }
        return items;

    private int resolveLedgerServerId(String name) {
        int hash = Math.abs((name == null ? "unknown" : name.toLowerCase(Locale.ROOT)).hashCode());
        return hash % 1024;
    }

    private long nextLedgerOperationNumericId(long nowMillis) {
        long timestamp = Math.max(nowMillis, ledgerCounterMillis);
        synchronized (ledgerCounter) {
            if (timestamp != ledgerCounterMillis) {
                ledgerCounterMillis = timestamp;
                ledgerCounter.set(0);
            }
            int counterValue = ledgerCounter.getAndIncrement();
            if (counterValue >= 4096) {
                ledgerCounterMillis = ledgerCounterMillis + 1L;
                ledgerCounter.set(0);
                counterValue = 0;
            }
            long epochMillis = ledgerCounterMillis - 1_700_000_000_000L;
            long timePart = (epochMillis & ((1L << 41) - 1)) << 22;
            long serverPart = ((long) ledgerServerId & 0x3FFL) << 12;
            long counterPart = counterValue & 0xFFFL;
            return timePart | serverPart | counterPart;
        }
    }

    private String ledgerPayload(String operationId, long sequence, long createdAt, String server, UUID playerUuid, String category, String reference,
                                 double goldDelta, Map<String, Integer> itemDelta, long previousHash, long entryHash, String payloadHash) {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("operation_id", operationId);
        yaml.set("sequence", sequence);
        yaml.set("created_at", createdAt);
        yaml.set("server", server);
        yaml.set("player", playerUuid.toString());
        yaml.set("category", category);
        yaml.set("reference", reference);
        yaml.set("gold_delta", goldDelta);
        yaml.set("items", itemDelta);
        yaml.set("previous_hash", previousHash);
        yaml.set("entry_hash", entryHash);
        yaml.set("payload_hash", payloadHash);
        return yaml.saveToString();
    }

    private void loadPendingLedgerEntries() {
        if (!Files.isDirectory(ledgerPendingDir)) {
            return;
        }
        List<LedgerEntry> recovered = new ArrayList<>();
        long chain = 0L;
        try (var paths = Files.list(ledgerPendingDir)) {
            paths.filter(path -> path.getFileName().toString().endsWith(".yml"))
                .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                .forEach(path -> {
                    try {
                        Properties props = readProperties(path);
                        String operationId = props.getProperty("operation_id", "");
                        long sequence = parseLong(props.getProperty("sequence"), 0L);
                        String playerRaw = props.getProperty("player", "");
                        String entryServer = props.getProperty("server", serverName);
                        String category = props.getProperty("category", "");
                        if (sequence <= 0L || playerRaw.isBlank() || category.isBlank()) {
                        YamlConfiguration yaml = readYaml(path);
                        String operationId = yaml.getString("operation_id", "");
                        long sequence = yaml.getLong("sequence", 0L);
                        String playerRaw = yaml.getString("player", "");
                        String entryServer = yaml.getString("server", "");
                        String category = yaml.getString("category", "");
                        if (sequence <= 0L || playerRaw.isBlank() || category.isBlank() || entryServer.isBlank()) {
                            return;
                        }
                        UUID playerUuid = UUID.fromString(playerRaw);
                        long createdAt = parseLong(props.getProperty("created_at"), System.currentTimeMillis());
                        String reference = props.getProperty("reference", "");
                        double goldDelta = parseDouble(props.getProperty("gold_delta"), 0.0D);
                        Map<String, Integer> items = parseLedgerItems(props.getProperty("items", ""));
                        long previousHash = parseLong(props.getProperty("previous_hash"), 0L);
                        long entryHash = parseLong(props.getProperty("entry_hash"), 0L);
                        long expectedHash = Objects.hash(sequence, createdAt, entryServer, playerUuid.toString(), category, reference, goldDelta, items, previousHash);
                        if (entryHash != 0L && entryHash != expectedHash) {
                            enterSafeMode("Pending ledger hash mismatch");
                            return;
                        }
                        if (entryHash == 0L) {
                            entryHash = expectedHash;
                        }
                        if (operationId.isBlank()) {
                            enterSafeMode("Pending ledger operation id missing");
                            return;
                        }
                        String payloadHash = props.getProperty("payload_hash", "");
                        LedgerPayloadSnapshot snapshot = new LedgerPayloadSnapshot(operationId, sequence, createdAt, entryServer, playerUuid, category, reference, goldDelta, items, previousHash, entryHash, "");
                        String payloadWithoutHash = ledgerPayload(snapshot);
                        String expectedPayloadHash = sha256(payloadWithoutHash);
                        if (!payloadHash.isBlank() && !payloadHash.equalsIgnoreCase(expectedPayloadHash)) {
                            enterSafeMode("Pending ledger payload hash mismatch");
                            return;
                        }
                        payloadHash = expectedPayloadHash;
                        String canonicalPayload = ledgerPayload(new LedgerPayloadSnapshot(operationId, sequence, createdAt, entryServer, playerUuid, category, reference, goldDelta, items, previousHash, entryHash, payloadHash));
                        recovered.add(new LedgerEntry(operationId, entryServer, sequence, createdAt, playerUuid, category, reference, goldDelta, items, canonicalPayload, payloadHash));
                    } catch (Exception exception) {
                        plugin.getLogger().warning("Unable to recover pending ledger entry " + path + ": " + exception.getMessage());
                    }
                });
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to recover pending ledger queue: " + exception.getMessage());
        }
        recovered.sort(Comparator.comparingLong(LedgerEntry::sequence));
        for (LedgerEntry entry : recovered) {
            Properties props = propertiesFromString(entry.payload());
            chain = parseLong(props.getProperty("entry_hash"), chain);
            ledgerQueue.add(entry);
        }
        ledgerHashChain.set(chain);
        if (!recovered.isEmpty()) {
            plugin.getLogger().warning("Recovered " + recovered.size() + " pending ledger entries for deterministic replay");
        }
    }

    private Map<String, Integer> negativeItemMap(Map<String, Integer> source) {
        Map<String, Integer> negative = new LinkedHashMap<>();
        if (source == null) {
            return negative;
        }
        for (Map.Entry<String, Integer> entry : source.entrySet()) {
            if (entry.getValue() != null && entry.getValue() > 0) {
                negative.put(entry.getKey(), -entry.getValue());
            }
        }
        return negative;
    }

    private void evaluateBackendSafety() {
        boolean mysqlEnabled = persistence.getBoolean("mysql.enabled", true);
        if (mysqlAuthorityRequired() && !mysqlEnabled) {
            enterSafeMode("MySQL authority disabled by configuration");
        }
        if (mysqlAuthorityRequired() && !mysqlDriverAvailable()) {
            enterSafeMode("MySQL JDBC driver unavailable");
        }
        if (mysqlAuthorityRequired() && !endpointReachable(persistence.getString("mysql.host", "127.0.0.1"), persistence.getInt("mysql.port", 3306), persistence.getInt("health_checks.mysql_connect_timeout_ms", 1000))) {
            enterSafeMode("MySQL backend unavailable");
        }
        boolean redisEnabled = persistence.getBoolean("redis.enabled", true);
        if (redisSessionRequired() && !redisEnabled) {
            enterSafeMode("Redis session authority disabled by configuration");
        }
        if (redisSessionRequired() && !endpointReachable(persistence.getString("redis.host", "127.0.0.1"), persistence.getInt("redis.port", 6379), persistence.getInt("health_checks.redis_connect_timeout_ms", 500))) {
            enterSafeMode("Redis session backend unavailable");
        }
        if (mysqlAuthorityRequired() && persistence.getBoolean("local_fallback.allow_writes_when_db_unavailable", false)) {
            enterSafeMode("Unsafe degraded local-authority mode is disabled in production");
        }
    }

    private void enterSafeMode(String reason) {
        if (!safeMode) {
            plugin.getLogger().severe("Entering safe mode: " + reason);
        }
        safeMode = true;
        safeModeReason = reason;
    }

    private void deletePathRecursively(Path path) {
        if (path == null || !Files.exists(path)) {
            return;
        }
        try (var walk = Files.walk(path)) {
            walk.sorted(java.util.Comparator.reverseOrder()).forEach(current -> {
                try {
                    Files.deleteIfExists(current);
                } catch (IOException exception) {
                    plugin.getLogger().warning("Unable to delete path " + current + ": " + exception.getMessage());
                }
            });
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to delete path tree " + path + ": " + exception.getMessage());
        }
    }

    private Path locateRoot(JavaPlugin plugin) {
        List<Path> seeds = new ArrayList<>();
        seeds.add(plugin.getDataFolder().toPath().toAbsolutePath());
        seeds.add(Paths.get("").toAbsolutePath());
        Path pluginParent = plugin.getDataFolder().toPath().toAbsolutePath().getParent();
        if (pluginParent != null) {
            seeds.add(pluginParent);
        }
        for (Path seed : seeds) {
            Path current = seed;
            while (current != null) {
                if (Files.isRegularFile(current.resolve("configs/network.yml"))) {
                    return current;
                }
                current = current.getParent();
            }
        }
        throw new IllegalStateException("Unable to locate project root with configs/network.yml");
    }

    private YamlConfiguration loadConfig(String name) {
        Path path = root.resolve("configs").resolve(name);
        if (!Files.isRegularFile(path)) {
            throw new IllegalStateException("Missing config: " + path);
        }
        return readYaml(path);
    }

    private YamlConfiguration loadOptionalConfig(String name) {
        Path path = root.resolve("configs").resolve(name);
        if (!Files.isRegularFile(path)) {
            return new YamlConfiguration();
        }
        return readYaml(path);
    }

    private YamlConfiguration readYaml(Path path) {
        YamlConfiguration yaml = new YamlConfiguration();
        try {
            if (Files.exists(path)) {
                yaml.loadFromString(Files.readString(path, StandardCharsets.UTF_8));
            }
        } catch (IOException | InvalidConfigurationException exception) {
            throw new IllegalStateException("Unable to read YAML: " + path, exception);
        }
        return yaml;
    }

    private String resolveServerName() {
        String cwd = Paths.get("").toAbsolutePath().getFileName().toString();
        if (network.contains("servers." + cwd)) {
            return cwd;
        }
        int serverPort = plugin.getServer().getPort();
        for (String key : keys(networkSection("servers"))) {
            String address = network.getString("servers." + key + ".address", "");
            if (address.endsWith(":" + serverPort)) {
                return key;
            }
        }
        Properties props = new Properties();
        Path serverProps = Paths.get("").toAbsolutePath().resolve("server.properties");
        if (Files.exists(serverProps)) {
            try (InputStream input = Files.newInputStream(serverProps)) {
                props.load(input);
            } catch (IOException ignored) {
            }
            String port = props.getProperty("server-port", "");
            for (String key : keys(networkSection("servers"))) {
                String address = network.getString("servers." + key + ".address", "");
                if (address.endsWith(":" + port)) {
                    return key;
                }
            }
        }
        return cwd;
    }

    private String resolveServerRole() {
        return network.getString("servers." + serverName + ".role", "unknown");
    }

    private void validateBackendBaseline() {
        Path current = Paths.get("").toAbsolutePath();
        Path serverProps = current.resolve("server.properties");
        if (!Files.exists(serverProps)) {
            enterSafeMode("Missing server.properties");
            return;
        }
        Properties props = new Properties();
        try (InputStream input = Files.newInputStream(serverProps)) {
            props.load(input);
            String onlineMode = props.getProperty("online-mode", "false");
            String serverIp = props.getProperty("server-ip", "127.0.0.1");
            if (exploit.getBoolean("network.backend_online_mode_must_be_false", true) && !"false".equalsIgnoreCase(onlineMode)) {
                enterSafeMode("Backend online-mode must be false behind Velocity");
            }
            if (exploit.getBoolean("network.direct_backend_join_block", true) && !"127.0.0.1".equals(serverIp)) {
                enterSafeMode("Backend server-ip must remain 127.0.0.1 for direct join protection");
            }
            if (network.getBoolean("proxy.advanced.accepts_transfers", true)) {
                enterSafeMode("Velocity transfers must remain disabled for deterministic routing");
            }
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to inspect server.properties: " + exception.getMessage());
            enterSafeMode("Unable to inspect server.properties");
        }
    }

    private RpgProfile loadProfile(UUID uuid, String name) {
        RpgProfile authoritative = loadProfileFromMySql(uuid, name);
        if (authoritative != null) {
            return authoritative;
        }
        if (mysqlAuthorityRequired()) {
            enterSafeMode("MySQL authoritative profile unavailable");
            return new RpgProfile(uuid, name);
        }
        if (persistence.getBoolean("local_fallback.enabled", true)) {
            Path path = profilePath(uuid);
            if (Files.exists(path)) {
                RpgProfile fallback = RpgProfile.fromYaml(uuid, name, readYaml(path));
                if (persistence.getBoolean("mysql.enabled", true)) {
                    persistProfileToMySql(fallback, 0L, false);
                }
                return fallback;
            }
        }
        return new RpgProfile(uuid, name);
    }

    private RpgGuild loadGuild(String key) {
        String normalized = normalizeGuild(key);
        RpgGuild authoritative = loadGuildFromMySql(normalized);
        if (authoritative != null) {
            return authoritative;
        }
        if (mysqlAuthorityRequired()) {
            enterSafeMode("MySQL authoritative guild unavailable");
            return new RpgGuild(normalized, "");
        }
        if (persistence.getBoolean("local_fallback.enabled", true)) {
            Path path = guildPath(normalized);
            if (Files.exists(path)) {
                RpgGuild fallback = RpgGuild.fromYaml(normalized, readYaml(path));
                if (persistence.getBoolean("mysql.enabled", true) && (!fallback.getOwnerUuid().isBlank() || !fallback.getMembersView().isEmpty())) {
                    persistGuildToMySql(fallback, 0L, false);
                }
                return fallback;
            }
        }
        return new RpgGuild(normalized, "");
    }

    private Path profilePath(UUID uuid) {
        return profileDir.resolve(uuid + ".yml");
    }

    private Path guildPath(String key) {
        return guildDir.resolve(normalizeGuild(key) + ".yml");
    }

    private void ensurePath(Path path) {
        try {
            Files.createDirectories(path);
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to create path: " + path, exception);
        }
    }

    private void writeYaml(Path path, String contents) {
        try {
            ensurePath(path.getParent());
            Path temp = path.resolveSibling(path.getFileName() + ".tmp");
            Files.writeString(temp, contents, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE);
            try (var channel = java.nio.channels.FileChannel.open(temp, StandardOpenOption.WRITE)) {
                channel.force(true);
            }
            try {
                Files.move(temp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException atomicFailure) {
                Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING);
            }
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to write file " + path + ": " + exception.getMessage());
        }
    }

    private boolean writeSession(RpgProfile profile, boolean online) {
        Path sessionPath = sessionDir.resolve(profile.getUuid() + ".yml");
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("uuid", profile.getUuid().toString());
        yaml.set("name", profile.getLastName());
        yaml.set("server", serverName);
        yaml.set("role", serverRole);
        yaml.set("online", online);
        yaml.set("guild", profile.getGuildName());
        yaml.set("active_dungeon", profile.getActiveDungeon());
        yaml.set("active_dungeon_instance", profile.getActiveDungeonInstanceId());
        yaml.set("active_dungeon_world", profile.getActiveDungeonWorld());
        yaml.set("updated_at", System.currentTimeMillis());
        String serialized = yaml.saveToString();
        if (redisSessionRequired()) {
            if (!persistence.getBoolean("redis.enabled", true)) {
                enterSafeMode("Redis session authority disabled by configuration");
                return false;
            }
            int holdSeconds = Math.max(15, exploit.getInt("progression.reconnect_state_hold_seconds", 30));
            boolean mirrored = writeRedisYamlValue("rpg:session:" + profile.getUuid(), holdSeconds, serialized);
            if (!mirrored) {
                enterSafeMode("Redis session backend unavailable");
                return false;
            }
        }
        if (persistence.getBoolean("local_fallback.enabled", true)) {
            writeYaml(sessionPath, serialized);
        }
        return true;
    }

    private YamlConfiguration yamlFromString(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }
        YamlConfiguration yaml = new YamlConfiguration();
        try {
            yaml.loadFromString(raw);
            return yaml;
        } catch (InvalidConfigurationException exception) {
            plugin.getLogger().warning("Unable to parse stored YAML payload: " + exception.getMessage());
            return null;
        }
    }

    private RpgProfile loadProfileFromMySql(UUID uuid, String defaultName) {
        if (!persistence.getBoolean("mysql.enabled", true)) {
            return null;
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                if (mysqlAuthorityRequired()) {
                    enterSafeMode("MySQL backend unavailable");
                }
                return null;
            }
            ensureMysqlSchema(connection);
            try (PreparedStatement statement = connection.prepareStatement("SELECT payload FROM rpg_profiles WHERE uuid = ?")) {
                statement.setString(1, uuid.toString());
                try (ResultSet resultSet = statement.executeQuery()) {
                    if (!resultSet.next()) {
                        return null;
                    }
                    YamlConfiguration yaml = yamlFromString(resultSet.getString("payload"));
                    if (yaml == null) {
                        return null;
                    }
                    return RpgProfile.fromYaml(uuid, defaultName, yaml);
                }
            }
        } catch (Exception exception) {
            plugin.getLogger().fine("MySQL profile read unavailable: " + exception.getMessage());
            if (mysqlAuthorityRequired()) {
                enterSafeMode("MySQL backend unavailable");
            }
            return null;
        }
    }

    private RpgGuild loadGuildFromMySql(String key) {
        if (!persistence.getBoolean("mysql.enabled", true)) {
            return null;
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                if (mysqlAuthorityRequired()) {
                    enterSafeMode("MySQL backend unavailable");
                }
                return null;
            }
            ensureMysqlSchema(connection);
            try (PreparedStatement statement = connection.prepareStatement("SELECT payload FROM rpg_guilds WHERE name = ?")) {
                statement.setString(1, normalizeGuild(key));
                try (ResultSet resultSet = statement.executeQuery()) {
                    if (!resultSet.next()) {
                        return null;
                    }
                    YamlConfiguration yaml = yamlFromString(resultSet.getString("payload"));
                    if (yaml == null) {
                        return null;
                    }
                    return RpgGuild.fromYaml(normalizeGuild(key), yaml);
                }
            }
        } catch (Exception exception) {
            plugin.getLogger().fine("MySQL guild read unavailable: " + exception.getMessage());
            if (mysqlAuthorityRequired()) {
                enterSafeMode("MySQL backend unavailable");
            }
            return null;
        }
    }

    private long readProfileDurableVersion(UUID uuid) {
        if (!persistence.getBoolean("mysql.enabled", true)) {
            return lastFlushedProfileVersion.getOrDefault(uuid, 0L);
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                return 0L;
            }
            ensureMysqlSchema(connection);
            try (PreparedStatement statement = connection.prepareStatement("SELECT updated_at FROM rpg_profiles WHERE uuid = ?")) {
                statement.setString(1, uuid.toString());
                try (ResultSet resultSet = statement.executeQuery()) {
                    if (resultSet.next()) {
                        return resultSet.getLong("updated_at");
                    }
                }
            }
        } catch (Exception ignored) {
            // fall back to in-memory flush watermark
        }
        return lastFlushedProfileVersion.getOrDefault(uuid, 0L);
    }

    private long readGuildDurableVersion(String key) {
        String normalized = normalizeGuild(key);
        if (normalized.isBlank()) {
            return 0L;
        }
        if (!persistence.getBoolean("mysql.enabled", true)) {
            return lastFlushedGuildVersion.getOrDefault(normalized, 0L);
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                return 0L;
            }
            ensureMysqlSchema(connection);
            try (PreparedStatement statement = connection.prepareStatement("SELECT updated_at FROM rpg_guilds WHERE name = ?")) {
                statement.setString(1, normalized);
                try (ResultSet resultSet = statement.executeQuery()) {
                    if (resultSet.next()) {
                        return resultSet.getLong("updated_at");
                    }
                }
            }
        } catch (Exception ignored) {
            // fall back to in-memory flush watermark
        }
        return lastFlushedGuildVersion.getOrDefault(normalized, 0L);
    }

    private boolean writeRedisYamlValue(String key, int ttlSeconds, String payload) {
        if (!persistence.getBoolean("redis.enabled", true)) {
            return false;
        }
        try {
            Object reply = redisCommand("SETEX", key, String.valueOf(Math.max(1, ttlSeconds)), payload == null ? "" : payload);
            return reply instanceof String value && "OK".equalsIgnoreCase(value);
        } catch (IOException exception) {
            plugin.getLogger().fine("Redis write unavailable: " + exception.getMessage());
            return false;
        }
    }

    private YamlConfiguration readRedisYamlValue(String key) {
        if (!persistence.getBoolean("redis.enabled", true)) {
            return null;
        }
        try {
            Object reply = redisCommand("GET", key);
            if (!(reply instanceof String payload) || payload.isBlank()) {
                return null;
            }
            return yamlFromString(payload);
        } catch (IOException exception) {
            plugin.getLogger().fine("Redis read unavailable: " + exception.getMessage());
            return null;
        }
    }

    private void deleteRedisKey(String key) {
        if (!persistence.getBoolean("redis.enabled", true)) {
            return;
        }
        try {
            redisCommand("DEL", key);
        } catch (IOException exception) {
            plugin.getLogger().fine("Redis delete unavailable: " + exception.getMessage());
        }
    }

    private Object redisCommand(String... args) throws IOException {
        String host = persistence.getString("redis.host", "127.0.0.1");
        int port = persistence.getInt("redis.port", 6379);
        int timeout = persistence.getInt("redis.timeout_ms", 1500);
        String passwordEnv = persistence.getString("redis.password_env", "RPG_REDIS_PASSWORD");
        String password = passwordEnv == null ? "" : System.getenv(passwordEnv);
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), timeout);
            socket.setSoTimeout(timeout);
            OutputStream output = socket.getOutputStream();
            InputStream input = socket.getInputStream();
            if (password != null && !password.isBlank()) {
                redisCommand(output, input, "AUTH", password);
            }
            redisCommand(output, input, "SELECT", String.valueOf(persistence.getInt("redis.database", 0)));
            return redisCommand(output, input, args);
        }
    }

    private Object redisCommand(OutputStream output, InputStream input, String... args) throws IOException {
        StringBuilder request = new StringBuilder();
        request.append('*').append(args.length).append("\r\n");
        for (String arg : args) {
            byte[] bytes = (arg == null ? "" : arg).getBytes(StandardCharsets.UTF_8);
            request.append('$').append(bytes.length).append("\r\n").append(arg == null ? "" : arg).append("\r\n");
        }
        output.write(request.toString().getBytes(StandardCharsets.UTF_8));
        output.flush();
        return readRedisReply(input);
    }

    private Object readRedisReply(InputStream input) throws IOException {
        int prefix = input.read();
        if (prefix == -1) {
            throw new IOException("Redis connection closed");
        }
        return switch (prefix) {
            case '+' -> readRedisLine(input);
            case '-' -> throw new IOException("Redis error: " + readRedisLine(input));
            case ':' -> Long.parseLong(readRedisLine(input));
            case '$' -> {
                int length = Integer.parseInt(readRedisLine(input));
                if (length < 0) {
                    yield null;
                }
                byte[] bytes = input.readNBytes(length);
                if (bytes.length != length) {
                    throw new IOException("Redis bulk reply truncated");
                }
                int cr = input.read();
                int lf = input.read();
                if (cr != '\r' || lf != '\n') {
                    throw new IOException("Redis bulk reply missing line ending");
                }
                yield new String(bytes, StandardCharsets.UTF_8);
            }
            case '*' -> {
                int count = Integer.parseInt(readRedisLine(input));
                List<Object> values = new ArrayList<>();
                for (int i = 0; i < count; i++) {
                    values.add(readRedisReply(input));
                }
                yield values;
            }
            default -> throw new IOException("Unsupported Redis reply prefix: " + (char) prefix);
        };
    }

    private String readRedisLine(InputStream input) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        while (true) {
            int value = input.read();
            if (value == -1) {
                throw new IOException("Redis connection closed while reading line");
            }
            if (value == '\r') {
                int next = input.read();
                if (next != '\n') {
                    throw new IOException("Malformed Redis line ending");
                }
                return buffer.toString(StandardCharsets.UTF_8);
            }
            buffer.write(value);
        }
    }

    private boolean mysqlAuthorityRequired() {
        return "mysql".equalsIgnoreCase(network.getString("data_flow.player_profile", ""))
            || "mysql".equalsIgnoreCase(network.getString("data_flow.inventory_authority", ""))
            || "mysql".equalsIgnoreCase(network.getString("data_flow.guild_state", ""))
            || "mysql".equalsIgnoreCase(network.getString("data_flow.economy_ledger", ""));
    }

    private boolean redisSessionRequired() {
        return "redis".equalsIgnoreCase(network.getString("data_flow.live_session_state", ""));
    }

    private void ensureMysqlSchema(Connection connection) throws Exception {
        if (mysqlSchemaReady) {
            return;
        }
        synchronized (this) {
            if (mysqlSchemaReady) {
                return;
            }
            try (Statement statement = connection.createStatement()) {
                statement.executeUpdate("CREATE TABLE IF NOT EXISTS rpg_profiles (uuid VARCHAR(36) PRIMARY KEY, last_name VARCHAR(32), guild_name VARCHAR(32), gold DOUBLE NOT NULL, payload LONGTEXT NOT NULL, updated_at BIGINT NOT NULL)");
                statement.executeUpdate("CREATE TABLE IF NOT EXISTS rpg_guilds (name VARCHAR(32) PRIMARY KEY, owner_uuid VARCHAR(36), member_count INT NOT NULL, bank_gold DOUBLE NOT NULL, payload LONGTEXT NOT NULL, updated_at BIGINT NOT NULL)");
                statement.executeUpdate("CREATE TABLE IF NOT EXISTS rpg_ledger (operation_id VARCHAR(64) PRIMARY KEY, server VARCHAR(64) NOT NULL, sequence_id BIGINT NOT NULL, created_at BIGINT NOT NULL, player_uuid VARCHAR(36) NOT NULL, category VARCHAR(64) NOT NULL, reference_id VARCHAR(128) NOT NULL, gold_delta DOUBLE NOT NULL, item_delta LONGTEXT NOT NULL, payload LONGTEXT NOT NULL, payload_hash VARCHAR(64) NOT NULL, UNIQUE KEY uq_server_sequence (server, sequence_id), UNIQUE KEY uq_payload_identity (server, sequence_id, payload_hash))");
                mysqlSchemaReady = true;
            }
        }
    }

    private PersistOutcome persistProfileAuthoritatively(RpgProfile profile, long expectedStoredVersion) {
        if (mysqlAuthorityRequired()) {
            return persistProfileToMySql(profile, expectedStoredVersion, true);
        }
        PersistOutcome optional = persistProfileToMySql(profile, expectedStoredVersion, false);
        return optional == PersistOutcome.UNAVAILABLE ? PersistOutcome.SUCCESS : optional;
    }

    private PersistOutcome persistGuildAuthoritatively(RpgGuild guild, long expectedStoredVersion) {
        if (mysqlAuthorityRequired()) {
            return persistGuildToMySql(guild, expectedStoredVersion, true);
        }
        PersistOutcome optional = persistGuildToMySql(guild, expectedStoredVersion, false);
        return optional == PersistOutcome.UNAVAILABLE ? PersistOutcome.SUCCESS : optional;
    }

    private PersistOutcome persistProfileToMySql(RpgProfile profile, long expectedStoredVersion, boolean required) {
        if (!persistence.getBoolean("mysql.enabled", true)) {
            if (required) {
                enterSafeMode("MySQL authority disabled by configuration");
            }
            return PersistOutcome.UNAVAILABLE;
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                if (required) {
                    enterSafeMode("MySQL backend unavailable");
                }
                return PersistOutcome.UNAVAILABLE;
            }
            ensureMysqlSchema(connection);
            String payload = profile.toYaml().saveToString();
            long version = profile.getUpdatedAt();
            if (expectedStoredVersion <= 0L) {
                try (PreparedStatement insert = connection.prepareStatement("INSERT INTO rpg_profiles (uuid, last_name, guild_name, gold, payload, updated_at) VALUES (?, ?, ?, ?, ?, ?)")) {
                    insert.setString(1, profile.getUuid().toString());
                    insert.setString(2, profile.getLastName());
                    insert.setString(3, profile.getGuildName());
                    insert.setDouble(4, profile.getGold());
                    insert.setString(5, payload);
                    insert.setLong(6, version);
                    if (insert.executeUpdate() > 0) {
                        return PersistOutcome.SUCCESS;
                    }
                } catch (java.sql.SQLIntegrityConstraintViolationException ignored) {
                    // fall through to CAS update
                }
            }
            try (PreparedStatement update = connection.prepareStatement(
                "UPDATE rpg_profiles SET last_name = ?, guild_name = ?, gold = ?, payload = ?, updated_at = ? WHERE uuid = ? AND updated_at = ?")) {
                update.setString(1, profile.getLastName());
                update.setString(2, profile.getGuildName());
                update.setDouble(3, profile.getGold());
                update.setString(4, payload);
                update.setLong(5, version);
                update.setString(6, profile.getUuid().toString());
                update.setLong(7, expectedStoredVersion);
                if (update.executeUpdate() > 0) {
                    return PersistOutcome.SUCCESS;
                }
            }
            try (PreparedStatement current = connection.prepareStatement("SELECT updated_at FROM rpg_profiles WHERE uuid = ?")) {
                current.setString(1, profile.getUuid().toString());
                try (ResultSet result = current.executeQuery()) {
                    if (result.next()) {
                        long durableVersion = result.getLong("updated_at");
                        if (durableVersion == version) {
                            return PersistOutcome.SUCCESS;
                        }
                        casConflictCount.incrementAndGet();
                        plugin.getLogger().warning("CAS profile write rejected for " + profile.getUuid() + " expected=" + expectedStoredVersion + " durable=" + durableVersion + " next=" + version);
                        return PersistOutcome.CONFLICT;
                    }
                }
            }
            casConflictCount.incrementAndGet();
            return PersistOutcome.CONFLICT;
        } catch (Exception exception) {
            plugin.getLogger().fine("MySQL profile persistence unavailable: " + exception.getMessage());
            if (required) {
                enterSafeMode("MySQL backend unavailable");
            }
            return PersistOutcome.UNAVAILABLE;
        }
    }

    private PersistOutcome persistGuildToMySql(RpgGuild guild, long expectedStoredVersion, boolean required) {
        if (!persistence.getBoolean("mysql.enabled", true)) {
            if (required) {
                enterSafeMode("MySQL authority disabled by configuration");
            }
            return PersistOutcome.UNAVAILABLE;
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                if (required) {
                    enterSafeMode("MySQL backend unavailable");
                }
                return PersistOutcome.UNAVAILABLE;
            }
            ensureMysqlSchema(connection);
            String payload = guild.toYaml().saveToString();
            long version = guild.getUpdatedAt();
            if (expectedStoredVersion <= 0L) {
                try (PreparedStatement insert = connection.prepareStatement("INSERT INTO rpg_guilds (name, owner_uuid, member_count, bank_gold, payload, updated_at) VALUES (?, ?, ?, ?, ?, ?)")) {
                    insert.setString(1, guild.getName());
                    insert.setString(2, guild.getOwnerUuid());
                    insert.setInt(3, guild.getMembersView().size());
                    insert.setDouble(4, guild.getBankGold());
                    insert.setString(5, payload);
                    insert.setLong(6, version);
                    if (insert.executeUpdate() > 0) {
                        return PersistOutcome.SUCCESS;
                    }
                } catch (java.sql.SQLIntegrityConstraintViolationException ignored) {
                    // fall through to CAS update
                }
            }
            try (PreparedStatement update = connection.prepareStatement(
                "UPDATE rpg_guilds SET owner_uuid = ?, member_count = ?, bank_gold = ?, payload = ?, updated_at = ? WHERE name = ? AND updated_at = ?")) {
                update.setString(1, guild.getOwnerUuid());
                update.setInt(2, guild.getMembersView().size());
                update.setDouble(3, guild.getBankGold());
                update.setString(4, payload);
                update.setLong(5, version);
                update.setString(6, guild.getName());
                update.setLong(7, expectedStoredVersion);
                if (update.executeUpdate() > 0) {
                    return PersistOutcome.SUCCESS;
                }
            }
            try (PreparedStatement current = connection.prepareStatement("SELECT updated_at FROM rpg_guilds WHERE name = ?")) {
                current.setString(1, guild.getName());
                try (ResultSet result = current.executeQuery()) {
                    if (result.next()) {
                        long durableVersion = result.getLong("updated_at");
                        if (durableVersion == version) {
                            return PersistOutcome.SUCCESS;
                        }
                        casConflictCount.incrementAndGet();
                        plugin.getLogger().warning("CAS guild write rejected for " + guild.getName() + " expected=" + expectedStoredVersion + " durable=" + durableVersion + " next=" + version);
                        return PersistOutcome.CONFLICT;
                    }
                }
            }
            casConflictCount.incrementAndGet();
            return PersistOutcome.CONFLICT;
        } catch (Exception exception) {
            plugin.getLogger().fine("MySQL guild persistence unavailable: " + exception.getMessage());
            if (required) {
                enterSafeMode("MySQL backend unavailable");
            }
            return PersistOutcome.UNAVAILABLE;
        }
    }

    private boolean deleteGuildFromMySql(String key) {
        if (!persistence.getBoolean("mysql.enabled", true)) {
            if (mysqlAuthorityRequired()) {
                enterSafeMode("MySQL authority disabled by configuration");
            }
            return !mysqlAuthorityRequired();
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                if (mysqlAuthorityRequired()) {
                    enterSafeMode("MySQL backend unavailable");
                    return false;
                }
                return false;
            }
            ensureMysqlSchema(connection);
            try (PreparedStatement statement = connection.prepareStatement("DELETE FROM rpg_guilds WHERE name = ?")) {
                statement.setString(1, normalizeGuild(key));
                statement.executeUpdate();
                return true;
            }
        } catch (Exception exception) {
            plugin.getLogger().fine("MySQL guild delete unavailable: " + exception.getMessage());
            if (mysqlAuthorityRequired()) {
                enterSafeMode("MySQL backend unavailable");
                return false;
            }
            return false;
        }
    }

    private void flushLedger() {
        ledgerLastFlushAt.set(System.currentTimeMillis());
        if (ledgerQueue.isEmpty()) {
            return;
        }
        List<LedgerEntry> pending = new ArrayList<>();
        int batch = Math.max(500, persistence.getInt("write_policy.ledger_max_entries_per_flush", 4000));
        for (int i = 0; i < batch; i++) {
            LedgerEntry entry = ledgerQueue.poll();
            if (entry == null) {
                break;
            }
            pending.add(entry);
        }
        if (pending.isEmpty()) {
            return;
        }
        int index = 0;
        for (; index < pending.size(); index++) {
            LedgerEntry entry = pending.get(index);
            if (!persistLedgerEntry(entry)) {
                break;
            }
            clearPendingLedgerEntry(entry);
            mirrorLedgerEntry(entry);
        }
        if (index < pending.size()) {
            for (int i = pending.size() - 1; i >= index; i--) {
                ledgerQueue.add(pending.get(i));
            }
        }
    }

    private void mirrorLedgerEntry(LedgerEntry entry) {
        if (!persistence.getBoolean("local_fallback.enabled", true)) {
            return;
        }
        String fileName = "ledger-" + LocalDate.now(ZoneId.systemDefault()) + ".log";
        String line = entry.sequence() + "|" + entry.createdAt() + "|" + serverName + "|" + entry.playerUuid() + "|" + entry.category() + "|" + entry.reference() + "|" + entry.goldDelta() + "|" + entry.itemDelta() + System.lineSeparator();
        appendAuditLine(fileName, line);
    }

    private boolean persistLedgerEntry(LedgerEntry entry) {
        boolean required = "mysql".equalsIgnoreCase(network.getString("data_flow.economy_ledger", ""));
        if (!persistence.getBoolean("mysql.enabled", true)) {
            if (required) {
                enterSafeMode("Economy ledger authority unavailable");
            }
            return !required;
        }
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                if (required) {
                    enterSafeMode("Economy ledger authority unavailable");
                }
                return !required;
            }
            ensureMysqlSchema(connection);
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO rpg_ledger (operation_id, server, sequence_id, created_at, player_uuid, category, reference_id, gold_delta, item_delta, payload, payload_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")) {
                statement.setString(1, entry.operationId());
                statement.setString(2, entry.server());
                statement.setLong(3, entry.sequence());
                statement.setLong(4, entry.createdAt());
                statement.setString(5, entry.playerUuid().toString());
                statement.setString(6, entry.category());
                statement.setString(7, entry.reference());
                statement.setDouble(8, entry.goldDelta());
                statement.setString(9, String.valueOf(entry.itemDelta()));
                statement.setString(10, entry.payload());
                statement.setString(11, entry.payloadHash());
                statement.executeUpdate();
                return true;
            }
        } catch (Exception exception) {
            if (isDuplicateLedgerSequence(exception)) {
                return validateDuplicateLedgerEntry(entry);
            }
            plugin.getLogger().fine("MySQL ledger write unavailable: " + exception.getMessage());
            if (required) {
                enterSafeMode("Economy ledger authority unavailable");
            }
            return !required;
        }
    }


    private boolean validateDuplicateLedgerEntry(LedgerEntry entry) {
        try (Connection connection = mysqlConnection()) {
            if (connection == null) {
                return false;
            }
            try (PreparedStatement statement = connection.prepareStatement("SELECT operation_id, server, sequence_id, payload_hash FROM rpg_ledger WHERE operation_id = ? OR (server = ? AND sequence_id = ?) LIMIT 2")) {
                statement.setString(1, entry.operationId());
                statement.setString(2, entry.server());
                statement.setLong(3, entry.sequence());
                try (ResultSet resultSet = statement.executeQuery()) {
                    boolean matchedByOperationId = false;
                    boolean matchedByServerSequence = false;
                    int rows = 0;
                    while (resultSet.next()) {
                        rows++;
                        String existingOperationId = resultSet.getString("operation_id");
                        String existingServer = resultSet.getString("server");
                        long existingSequence = resultSet.getLong("sequence_id");
                        String existingHash = resultSet.getString("payload_hash");
                        if (existingOperationId != null && existingOperationId.equalsIgnoreCase(entry.operationId())) {
                            matchedByOperationId = true;
                        }
                        if (existingServer != null && existingServer.equalsIgnoreCase(entry.server()) && existingSequence == entry.sequence()) {
                            matchedByServerSequence = true;
                        }
                        if (existingHash == null || !existingHash.equalsIgnoreCase(entry.payloadHash())) {
                            enterSafeMode("Ledger duplicate payload mismatch");
                            return false;
                        }
                    }
                    if (rows > 1) {
                        enterSafeMode("Ledger duplicate identity collision");
                        return false;
                    }
                    if (matchedByOperationId || matchedByServerSequence) {
                        return true;
                    }
                    enterSafeMode("Ledger duplicate unknown identity");
                    return false;
                }
            }
        } catch (Exception exception) {
            plugin.getLogger().warning("Ledger duplicate validation failed: " + exception.getMessage());
            return false;
        }
    }

    private boolean isDuplicateLedgerSequence(Exception exception) {
        Throwable current = exception;
        while (current != null) {
            if (current instanceof java.sql.SQLException sqlException) {
                String state = sqlException.getSQLState();
                String message = sqlException.getMessage() == null ? "" : sqlException.getMessage().toLowerCase(Locale.ROOT);
                if ((state != null && state.startsWith("23")) || message.contains("duplicate") || message.contains("primary")) {
                    return true;
                }
            }
            current = current.getCause();
        }
        return false;
    }

    private void persistPendingLedgerEntry(LedgerEntry entry) {
        if (!persistence.getBoolean("local_fallback.enabled", true)) {
            return;
        }
        writeYaml(ledgerPendingDir.resolve(entry.operationId() + ".yml"), entry.payload());
    }

    private void clearPendingLedgerEntry(LedgerEntry entry) {
        try {
            Files.deleteIfExists(ledgerPendingDir.resolve(entry.operationId() + ".yml"));
            Files.deleteIfExists(ledgerPendingDir.resolve(entry.sequence() + ".yml"));
        } catch (IOException exception) {
            plugin.getLogger().warning("Unable to clear pending ledger entry " + entry.operationId() + ": " + exception.getMessage());
        }
    }

    private void recordDbLatency(long nanos, boolean success) {
        dbOperationCount.incrementAndGet();
        dbLatencyTotalNanos.addAndGet(Math.max(0L, nanos));
        dbLatencyMaxNanos.accumulateAndGet(Math.max(0L, nanos), Math::max);
        if (!success) {
            dbOperationErrors.incrementAndGet();
        }
    }

    private boolean mysqlDriverAvailable() {
        if (mysqlDriverReady) {
            return true;
        }
        try {
            Class.forName("com.mysql.cj.jdbc.Driver");
            mysqlDriverReady = true;
            return true;
        } catch (ClassNotFoundException exception) {
            if (!mysqlDriverUnavailableLogged) {
                mysqlDriverUnavailableLogged = true;
                plugin.getLogger().severe("MySQL JDBC driver unavailable: " + exception.getMessage());
            }
            return false;
        }
    }

    private Connection mysqlConnection() {
        HikariDataSource pool = mysqlPool();
        if (pool == null) {
            recordDbLatency(0L, false);
            return null;
        }
        long started = System.nanoTime();
        try {
            Connection connection = pool.getConnection();
            recordDbLatency(System.nanoTime() - started, true);
            return connection;
        } catch (Exception exception) {
            recordDbLatency(System.nanoTime() - started, false);
            plugin.getLogger().fine("MySQL connection unavailable: " + exception.getMessage());
            return null;
        }
    }

    private synchronized HikariDataSource mysqlPool() {
        if (mysqlPool != null && !mysqlPool.isClosed()) {
            return mysqlPool;
        }
        if (!mysqlDriverAvailable()) {
            return null;
        }
        String passwordEnv = persistence.getString("mysql.password_env", "RPG_MYSQL_PASSWORD");
        String password = passwordEnv == null ? "" : System.getenv(passwordEnv);
        String host = persistence.getString("mysql.host", "127.0.0.1");
        int port = persistence.getInt("mysql.port", 3306);
        String database = persistence.getString("mysql.database", "rpg_network");
        String username = persistence.getString("mysql.username", "rpg_app");
        int timeoutMs = Math.max(500, persistence.getInt("mysql.pool.connection_timeout_ms", 3000));
        int maxPool = Math.max(4, persistence.getInt("mysql.pool.max_size", 16));
        String url = "jdbc:mysql://" + host + ":" + port + "/" + database
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC"
            + "&connectTimeout=" + timeoutMs
            + "&socketTimeout=" + timeoutMs;
        try {
            HikariConfig config = new HikariConfig();
            config.setJdbcUrl(url);
            config.setUsername(username);
            config.setPassword(password == null ? "" : password);
            config.setDriverClassName("com.mysql.cj.jdbc.Driver");
            config.setMaximumPoolSize(maxPool);
            config.setMinimumIdle(Math.min(4, maxPool));
            config.setConnectionTimeout(timeoutMs);
            config.setValidationTimeout(timeoutMs);
            config.setPoolName("rpg-core-" + serverName);
            mysqlPool = new HikariDataSource(config);
            return mysqlPool;
        } catch (Exception exception) {
            plugin.getLogger().fine("MySQL pool unavailable: " + exception.getMessage());
            return null;
        }
    }

    private synchronized void closeMysqlPool() {
        if (mysqlPool != null) {
            mysqlPool.close();
            mysqlPool = null;
        }
    }

    private void writeHealthSnapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("server", serverName);
        yaml.set("role", serverRole);
        yaml.set("profiles_cached", profiles.size());
        yaml.set("profiles_dirty", dirtyProfiles.size());
        yaml.set("guilds_cached", guilds.size());
        yaml.set("active_dungeons", activeDungeonCount());
        yaml.set("active_instances", activeInstanceCount());
        yaml.set("orphan_instances", orphanInstanceCount());
        yaml.set("orphan_instances_cleaned_total", orphanInstancesCleaned.get());
        yaml.set("instance_allocation_latency_ms_avg", allocationLatencyMsAvg());
        yaml.set("instance_allocation_latency_ms_max", allocationLatencyMsMax());
        yaml.set("managed_entities", managedEntityTotalCount());
        yaml.set("entity_pressure", entityPressure());
        yaml.set("entity_spawn_denied", managedEntitySpawnDeniedCount());
        yaml.set("safe_mode", safeMode);
        yaml.set("safe_mode_reason", safeModeReason);
        yaml.set("mysql_enabled", persistence.getBoolean("mysql.enabled", true));
        yaml.set("mysql_driver_available", mysqlDriverAvailable());
        yaml.set("mysql_authority_required", mysqlAuthorityRequired());
        yaml.set("mysql_reachable", endpointReachable(persistence.getString("mysql.host", "127.0.0.1"), persistence.getInt("mysql.port", 3306), 500));
        yaml.set("redis_enabled", persistence.getBoolean("redis.enabled", true));
        yaml.set("redis_authority_required", redisSessionRequired());
        yaml.set("redis_reachable", endpointReachable(persistence.getString("redis.host", "127.0.0.1"), persistence.getInt("redis.port", 6379), 500));
        yaml.set("online_players", Bukkit.getOnlinePlayers().size());
        yaml.set("ledger_queue_pending", ledgerQueueDepth());
        yaml.set("ledger_pending_files", pendingLedgerFileCount());
        yaml.set("db_operations_total", dbOperationCount());
        yaml.set("db_operation_errors_total", dbOperationErrorCount());
        yaml.set("db_latency_ms_avg", dbLatencyMsAvg());
        yaml.set("db_latency_ms_max", dbLatencyMsMax());
        yaml.set("transfer_fence_rejects", transferBarrierRejectCount());
        yaml.set("cas_conflicts", casConflictCount());
        yaml.set("reward_duplicate_suppressed", rewardDuplicateSuppressionCount());
        yaml.set("ledger_last_flush_at", ledgerLastFlushAt.get());
        writeYaml(runtimeDir.resolve("status").resolve(serverName + ".yml"), yaml.saveToString());
    }

    private boolean endpointReachable(String host, int port, int timeoutMs) {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), timeoutMs);
            return true;
        } catch (IOException ignored) {
            return false;
        }
    }

    private String sha256(String payload) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest((payload == null ? "" : payload).getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder();
            for (byte value : hash) {
                builder.append(String.format("%02x", value));
            }
            return builder.toString();
        } catch (Exception exception) {
            return "";
        }
    }

    private YamlConfiguration networkSection(String path) {
        YamlConfiguration yaml = new YamlConfiguration();
        ConfigurationSection section = network.getConfigurationSection(path);
        if (section != null) {
            for (String key : section.getKeys(false)) {
                yaml.set(key, section.get(key));
            }
        }
        return yaml;
    }

    private long parseLong(String value, long fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return Long.parseLong(value.trim());
        } catch (NumberFormatException exception) {
            return fallback;
        }
    }

    private double parseDouble(String value, double fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return Double.parseDouble(value.trim());
        } catch (NumberFormatException exception) {
            return fallback;
        }
    }

    private Properties propertiesFromString(String raw) {
        Properties properties = new Properties();
        if (raw == null || raw.isBlank()) {
            return properties;
        }
        try (InputStream stream = new java.io.ByteArrayInputStream(raw.getBytes(StandardCharsets.UTF_8))) {
            properties.load(stream);
        } catch (IOException ignored) {
        }
        return properties;
    }

    private Properties readProperties(Path path) {
        Properties properties = new Properties();
        if (!Files.exists(path)) {
            return properties;
        }
        try (InputStream stream = Files.newInputStream(path)) {
            properties.load(stream);
        } catch (IOException exception) {
            YamlConfiguration yaml = readYaml(path);
            properties.setProperty("operation_id", yaml.getString("operation_id", ""));
            properties.setProperty("sequence", Long.toString(yaml.getLong("sequence", 0L)));
            properties.setProperty("created_at", Long.toString(yaml.getLong("created_at", 0L)));
            properties.setProperty("server", yaml.getString("server", serverName));
            properties.setProperty("player", yaml.getString("player", ""));
            properties.setProperty("category", yaml.getString("category", ""));
            properties.setProperty("reference", yaml.getString("reference", ""));
            properties.setProperty("gold_delta", Double.toString(yaml.getDouble("gold_delta", 0.0D)));
            StringJoiner itemJoiner = new StringJoiner(",");
            for (Map.Entry<String, Integer> item : intMap(yaml.getConfigurationSection("items")).entrySet()) {
                itemJoiner.add(item.getKey() + ":" + item.getValue());
            }
            properties.setProperty("items", itemJoiner.toString());
            properties.setProperty("previous_hash", Long.toString(yaml.getLong("previous_hash", 0L)));
            properties.setProperty("entry_hash", Long.toString(yaml.getLong("entry_hash", 0L)));
            properties.setProperty("payload_hash", yaml.getString("payload_hash", ""));
        }
        return properties;
    }
}
