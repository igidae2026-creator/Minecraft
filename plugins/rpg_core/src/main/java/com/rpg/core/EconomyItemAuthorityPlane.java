package com.rpg.core;

import org.bukkit.configuration.file.YamlConfiguration;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Ledger + unique-item anti-duplication substrate for high-value economic state.
 */
public final class EconomyItemAuthorityPlane {
    public record LedgerMutation(String operationId, UUID ownerId, String category, String reference,
                                 double goldDelta, Map<String, Integer> itemDelta,
                                 String actor, long createdAt, String previousHash, String entryHash) {}

    public record ItemLineage(String itemInstanceId, String archetype, UUID mintedFor,
                              String mintSource, String ownerRef, String state,
                              long mintedAt, long updatedAt, List<String> history) {}

    private final ConcurrentLinkedQueue<LedgerMutation> ledger = new ConcurrentLinkedQueue<>();
    private final ConcurrentMap<String, LedgerMutation> opIndex = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, ItemLineage> itemLineage = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, ItemLineage> quarantine = new ConcurrentHashMap<>();

    private final AtomicLong duplicateMismatchCount = new AtomicLong();
    private final AtomicLong quarantineCount = new AtomicLong();

    public synchronized LedgerMutation appendMutation(String operationId, UUID ownerId, String category,
                                                      String reference, double goldDelta, Map<String, Integer> itemDelta,
                                                      String actor) {
        String op = operationId == null || operationId.isBlank() ? UUID.randomUUID().toString() : operationId;
        String previousHash = ledger.peek() == null ? "GENESIS" : ledger.stream().reduce((a, b) -> b).map(LedgerMutation::entryHash).orElse("GENESIS");
        Map<String, Integer> normalized = new LinkedHashMap<>();
        if (itemDelta != null) {
            itemDelta.forEach((k, v) -> normalized.put(k.toLowerCase(Locale.ROOT), v));
        }

        String payload = ownerId + "|" + normalize(category) + "|" + normalize(reference) + "|" + goldDelta + "|" + normalized + "|" + normalize(actor) + "|" + previousHash;
        String hash = sha256(payload);
        LedgerMutation existing = opIndex.get(op);
        if (existing != null) {
            if (!existing.entryHash().equals(hash)) {
                duplicateMismatchCount.incrementAndGet();
                throw new IllegalStateException("Ledger duplicate payload mismatch for operation=" + op);
            }
            return existing;
        }

        LedgerMutation mutation = new LedgerMutation(op, ownerId, normalize(category), normalize(reference), goldDelta, normalized,
            normalize(actor), Instant.now().toEpochMilli(), previousHash, hash);
        opIndex.put(op, mutation);
        ledger.add(mutation);
        return mutation;
    }

    public ItemLineage mintItem(String archetype, UUID mintedFor, String mintSource, String ownerRef) {
        String itemId = "itm_" + UUID.randomUUID().toString().replace("-", "");
        List<String> history = new ArrayList<>();
        long now = Instant.now().toEpochMilli();
        history.add(now + ":mint:" + normalize(mintSource) + ":owner=" + normalize(ownerRef));
        ItemLineage item = new ItemLineage(itemId, normalize(archetype), mintedFor, normalize(mintSource), normalize(ownerRef), "ACTIVE", now, now, history);
        itemLineage.put(itemId, item);
        return item;
    }

    public ItemLineage transferItem(String itemInstanceId, String nextOwnerRef, String source) {
        ItemLineage existing = itemLineage.get(itemInstanceId);
        if (existing == null) {
            return null;
        }
        if ("QUARANTINED".equals(existing.state())) {
            return existing;
        }
        long now = Instant.now().toEpochMilli();
        List<String> history = new ArrayList<>(existing.history());
        history.add(now + ":transfer:" + normalize(source) + ":owner=" + normalize(nextOwnerRef));
        ItemLineage next = new ItemLineage(existing.itemInstanceId(), existing.archetype(), existing.mintedFor(), existing.mintSource(),
            normalize(nextOwnerRef), existing.state(), existing.mintedAt(), now, history);
        itemLineage.put(next.itemInstanceId(), next);
        return next;
    }

    public void quarantineItem(String itemInstanceId, String reason) {
        ItemLineage existing = itemLineage.get(itemInstanceId);
        if (existing == null) {
            return;
        }
        long now = Instant.now().toEpochMilli();
        List<String> history = new ArrayList<>(existing.history());
        history.add(now + ":quarantine:" + normalize(reason));
        ItemLineage quarantined = new ItemLineage(existing.itemInstanceId(), existing.archetype(), existing.mintedFor(), existing.mintSource(),
            existing.ownerRef(), "QUARANTINED", existing.mintedAt(), now, history);
        itemLineage.put(itemInstanceId, quarantined);
        quarantine.put(itemInstanceId, quarantined);
        quarantineCount.incrementAndGet();
    }

    public YamlConfiguration snapshot() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("ledger_entries", ledger.size());
        yaml.set("ledger_duplicate_payload_mismatch", duplicateMismatchCount.get());
        yaml.set("tracked_items", itemLineage.size());
        yaml.set("quarantined_items", quarantine.size());
        yaml.set("quarantine_total", quarantineCount.get());
        return yaml;
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder();
            for (byte b : hash) {
                builder.append(String.format("%02x", b));
            }
            return builder.toString();
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 unavailable", exception);
        }
    }
}
