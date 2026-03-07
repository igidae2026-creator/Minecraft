Append-only artifact log

- 2026-03-06: Replaced plugin skeletons with working runtime modules and central core service.
- 2026-03-06: Added cached profile/guild persistence with local fallback, MySQL mirroring, Redis session mirroring, and audit snapshots.
- 2026-03-06: Added runtime dungeon, boss, quest, guild, skill, economy, event, and metrics logic.
- 2026-03-06: Added events config, plugin deployment matrix, and expanded operational scripts.
- 2026-03-06: Expanded tests for ops tooling, persistence runtime, plugin contracts, events, and core runtime wiring.
- 2026-03-07: Hardened authority coordination with explicit EXPIRED transfer-ticket state accounting, session/ticket expiry sweeps, and fixed instance boot orchestration to eliminate recursive boot calls.
