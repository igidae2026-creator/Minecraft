Append-only artifact log

- 2026-03-06: Replaced plugin skeletons with working runtime modules and central core service.
- 2026-03-06: Added cached profile/guild persistence with local fallback, MySQL mirroring, Redis session mirroring, and audit snapshots.
- 2026-03-06: Added runtime dungeon, boss, quest, guild, skill, economy, event, and metrics logic.
- 2026-03-06: Added events config, plugin deployment matrix, and expanded operational scripts.
- 2026-03-06: Expanded tests for ops tooling, persistence runtime, plugin contracts, events, and core runtime wiring.
- 2026-03-07: Hardened authority coordination with explicit EXPIRED transfer-ticket state accounting, session/ticket expiry sweeps, and fixed instance boot orchestration to eliminate recursive boot calls.
- 2026-03-08: Repaired authoritative instance boot and pending-ledger replay paths that previously violated deterministic runtime/replay guarantees.
- 2026-03-08: Added runtime gameplay artifact exports, policy registry persistence, and integrity validation surfaces for Genesis-aligned exploration/governance outputs.
- 2026-03-08: Added high-value item authority manifests with lineage-backed mint/transfer/consume tracking and exploit/quarantine escalation on impossible ownership.
- 2026-03-08: Hardened value-moving paths with durability-boundary rollback on delayed commit for rewards, upgrades, guild deposits, and admin mutations.
- 2026-03-08: Replaced Redis-authority config fiction with truthful in-repo session authority semantics plus optional Redis mirroring, and added explicit session/transfer substrate classes.
- 2026-03-08: Added first-class gameplay artifact, governance policy, and exploit detector registries plus new runtime exports under `runtime_data/coordination`, `runtime_data/experiments`, and `runtime_data/incidents`.
- 2026-03-08: Added runtime truth validation, reconciliation tooling, recovery/orchestration scripts, and runbook surfaces aligned to the implemented guarantees.
- 2026-03-08: Added first-class experiment, policy, pressure, and knowledge registries with runtime exports under `runtime_data/experiments`, `runtime_data/policies`, `runtime_data/status`, and `runtime_data/knowledge`.
- 2026-03-08: Expanded artifact registry classes to cover experiment results, governance decisions, and compensation/recovery actions with usefulness scoring for future retrieval.
- 2026-03-08: Added operator summary surfaces and behavioral fault-injection tests for transfer quarantine, split-brain detection, knowledge export visibility, and runtime summary aggregation.
