# Exploration OS Framing

This repository may contain runtime, platform, adapter, and consumer automation work, but its higher identity is still `METAOS as an exploration OS`.

Use this framing before making platform or runtime design decisions:

- Treat the current work as `runtime/platform layer`, not as the top-level identity.
- The higher-order constraints remain `exploration`, `lineage`, `replayability`, and `append-only truth`.
- Prefer designs that preserve artifact history, deterministic reconstruction, and multi-lineage evolution over designs that only optimize throughput or convenience.
- Do not let supervisor, queue, adapter, or policy machinery weaken replay, provenance, or append-only guarantees.
- If a platform shortcut conflicts with exploration traceability, lineage preservation, or replay restore, the shortcut loses.
- New domains and consumers should attach through adapters and contracts without mutating the exploration core.

Short rule:

`Platform work is valid, but it must stay subordinate to exploration OS invariants.`
