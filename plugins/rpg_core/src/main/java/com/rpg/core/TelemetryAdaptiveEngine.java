package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class TelemetryAdaptiveEngine {
    public enum SignalType {
        DUNGEON_COMPLETION_TIME,
        PLAYER_DEATH_RATE,
        EVENT_JOIN_RATE,
        PLAYER_SESSION_LENGTH,
        QUEUE_TIME,
        PLAYER_CHURN_SIGNAL
    }

    public record TelemetrySample(
        SignalType type,
        double value,
        String subject,
        long capturedAt
    ) {}

    public record AdaptiveState(
        double difficultyMultiplier,
        double rewardWeightMultiplier,
        double eventFrequencyMultiplier,
        double matchmakingRangeMultiplier,
        long capturedAt,
        String lastReason
    ) {}

    private final YamlConfiguration config;
    private final Map<SignalType, Deque<TelemetrySample>> samples = new LinkedHashMap<>();
    private volatile AdaptiveState state = new AdaptiveState(1.0D, 1.0D, 1.0D, 1.0D, Instant.now().toEpochMilli(), "initial");

    public TelemetryAdaptiveEngine(YamlConfiguration config) {
        this.config = config;
        for (SignalType type : SignalType.values()) {
            samples.put(type, new ArrayDeque<>());
        }
    }

    public void ingest(SignalType type, double value, String subject) {
        if (type == null || Double.isNaN(value) || Double.isInfinite(value)) {
            return;
        }
        Deque<TelemetrySample> deque = samples.get(type);
        if (deque == null) {
            return;
        }
        deque.addLast(new TelemetrySample(type, value, normalize(subject), Instant.now().toEpochMilli()));
        int max = Math.max(16, config.getInt("telemetry.max_samples_per_signal", 256));
        while (deque.size() > max) {
            deque.removeFirst();
        }
    }

    public AdaptiveState recompute(double pressureComposite, double completionRate) {
        double difficulty = clamp(state.difficultyMultiplier()
            + difficultyDelta()
            - pressurePenalty(pressureComposite), config.getDouble("difficulty.min_multiplier", 0.75D), config.getDouble("difficulty.max_multiplier", 1.35D));
        double rewards = clamp(state.rewardWeightMultiplier()
            + rewardDelta(completionRate, pressureComposite), config.getDouble("rewards.min_multiplier", 0.80D), config.getDouble("rewards.max_multiplier", 1.20D));
        double events = clamp(state.eventFrequencyMultiplier()
            + eventDelta(pressureComposite), config.getDouble("events.min_frequency_multiplier", 0.70D), config.getDouble("events.max_frequency_multiplier", 1.40D));
        double matchmaking = clamp(state.matchmakingRangeMultiplier()
            + matchmakingDelta(), config.getDouble("matchmaking.min_range_multiplier", 0.85D), config.getDouble("matchmaking.max_range_multiplier", 1.30D));
        state = new AdaptiveState(difficulty, rewards, events, matchmaking, Instant.now().toEpochMilli(),
            "difficulty=" + String.format(Locale.US, "%.2f", difficulty)
                + ", rewards=" + String.format(Locale.US, "%.2f", rewards)
                + ", events=" + String.format(Locale.US, "%.2f", events)
                + ", matchmaking=" + String.format(Locale.US, "%.2f", matchmaking));
        return state;
    }

    public AdaptiveState current() {
        return state;
    }

    public double average(SignalType type) {
        Deque<TelemetrySample> deque = samples.get(type);
        if (deque == null || deque.isEmpty()) {
            return 0.0D;
        }
        double total = 0.0D;
        for (TelemetrySample sample : deque) {
            total += sample.value();
        }
        return total / deque.size();
    }

    public int recentCount(SignalType type) {
        Deque<TelemetrySample> deque = samples.get(type);
        return deque == null ? 0 : deque.size();
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("difficulty_multiplier", state.difficultyMultiplier());
        yaml.set("reward_weight_multiplier", state.rewardWeightMultiplier());
        yaml.set("event_frequency_multiplier", state.eventFrequencyMultiplier());
        yaml.set("matchmaking_range_multiplier", state.matchmakingRangeMultiplier());
        yaml.set("captured_at", state.capturedAt());
        yaml.set("last_reason", state.lastReason());
        Map<String, Object> telemetry = new LinkedHashMap<>();
        for (SignalType type : SignalType.values()) {
            telemetry.put(type.name().toLowerCase(Locale.ROOT), Map.of(
                "count", recentCount(type),
                "avg", average(type)
            ));
        }
        yaml.set("telemetry", telemetry);
        return yaml;
    }

    private double difficultyDelta() {
        double completionSeconds = average(SignalType.DUNGEON_COMPLETION_TIME);
        double deathRate = average(SignalType.PLAYER_DEATH_RATE);
        double step = config.getDouble("difficulty.step", 0.05D);
        if (completionSeconds > 0.0D && completionSeconds < config.getDouble("difficulty.fast_completion_seconds", 240.0D) && deathRate <= config.getDouble("difficulty.low_death_rate", 0.10D)) {
            return step;
        }
        if ((completionSeconds > config.getDouble("difficulty.slow_completion_seconds", 720.0D))
            || deathRate >= config.getDouble("difficulty.high_death_rate", 0.35D)) {
            return -step;
        }
        return 0.0D;
    }

    private double rewardDelta(double completionRate, double pressureComposite) {
        double step = config.getDouble("rewards.step", 0.03D);
        if (completionRate > 0.0D && completionRate < config.getDouble("rewards.low_completion_rate", 0.45D)) {
            return step;
        }
        if (pressureComposite >= config.getDouble("rewards.inflation_pressure", 0.70D)) {
            return -step;
        }
        return 0.0D;
    }

    private double eventDelta(double pressureComposite) {
        double joinRate = average(SignalType.EVENT_JOIN_RATE);
        double churn = average(SignalType.PLAYER_CHURN_SIGNAL);
        double queue = average(SignalType.QUEUE_TIME);
        double step = config.getDouble("events.step", 0.05D);
        if (joinRate < config.getDouble("events.low_join_rate", 0.30D) || churn >= 1.0D) {
            return step;
        }
        if (pressureComposite >= config.getDouble("safety.max_combined_pressure", 0.90D) || queue > config.getDouble("matchmaking.high_queue_seconds", 45.0D)) {
            return -step;
        }
        return 0.0D;
    }

    private double matchmakingDelta() {
        double queue = average(SignalType.QUEUE_TIME);
        double step = config.getDouble("matchmaking.step", 0.05D);
        if (queue > config.getDouble("matchmaking.high_queue_seconds", 45.0D)) {
            return step;
        }
        if (queue > 0.0D && queue < (config.getDouble("matchmaking.high_queue_seconds", 45.0D) / 2.0D)) {
            return -step;
        }
        return 0.0D;
    }

    private double pressurePenalty(double pressureComposite) {
        if (pressureComposite >= config.getDouble("safety.max_combined_pressure", 0.90D)) {
            return config.getDouble("difficulty.step", 0.05D);
        }
        return 0.0D;
    }

    private double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }

    private String normalize(String raw) {
        return raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
    }
}
