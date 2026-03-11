# AUTONOMY_TARGET

## Purpose

This document isolates the autonomy and quality bar for the repository.
It defines the unattended execution standard separately from ad hoc operator instructions.
For layer positioning and higher-order design constraints, read [EXPLORATION_OS_FRAMING.md](/home/meta_os/Minecraft/EXPLORATION_OS_FRAMING.md) first.

## Target Standard

- The target is a 24-hour autonomous loop that keeps producing high-quality outputs with effectively no routine human intervention.
- Human involvement is allowed, but it must not be required for routine continuation.
- The desired steady state is that human intervention adds little or no meaningful quality gain over the system's default output.
- Human involvement should progressively shift from active production to approval, audit, and rare correction.
- Automation limited only to already-included repository scope is not enough; the outer loop must also evaluate newly arriving material, decide whether it belongs in scope, and promote it automatically when it clears quality and relevance gates.
- The system should continuously raise, reject, defer, or promote work items and source material without waiting for manual triage.

## Current Minecraft Goal

- The active repository goal is not only runtime steadiness.
- The current direct target is to push Minecraft service completeness upward while keeping Final Threshold closure intact.
- Progress is counted only if player-facing completeness rises without breaking append-only truth, lineage, replayability, or fail-closed governance.
- The current uplift path is:
  1. deepen gameplay progression through longer quest chains, denser dungeon variations, and stronger seasonal arcs
  2. strengthen onboarding, social, and live-ops re-entry loops
  3. keep anti-cheat, recovery, and progression trust coupled so completeness gains do not rely on unsafe shortcuts
  4. preserve bundle, soak, artifact, and final-threshold closure while the player-facing layer grows
- A content or gameplay increase that lowers governance quality or breaks replayable operating truth does not count as progress.
- A governance surface that stays green while player-facing completeness stalls also does not count as success.

## Runtime Success Condition

- The current success condition is:
  - `final_threshold_eval.json` remains ready
  - repo/content/minecraft bundles remain governed
  - player-facing completeness keeps rising
  - human marginal gain stays near zero on the operating surface
- Until those hold together, the target is still in progress.

## Evaluation Gate

- If the system still depends on frequent operator steering to maintain runtime quality, the target has not yet been met.
- Automation, deployment, validation, and recovery steps should be judged by unattended operation without quality collapse.
- Quality gates should prefer replayable runs, low review noise, and stable rerun behavior over manual babysitting.
- If newly ingested material still needs a person to decide routine scope selection, prioritization, or promotion into the active loop, the target has not yet been met.

## Operational Implications

- Persist intent, progress, and resume state in repository files instead of relying on chat memory.
- Prefer resumable loops, manifests, ledgers, checkpoints, and structured artifacts over conversational continuation.
- Treat automation changes as suspect if they increase dependence on manual steering.
- Add an outer ingestion and triage layer that can classify new inputs, bind them to the right subsystem, and either reject, sandbox, or promote them without operator involvement.
- Judge autonomy progress against the stricter bar of "human intervention produces negligible additional quality gain," not merely "the existing scripts can run unattended."
- Prefer a resident supervisor process with heartbeat, resumable state, and append-only logs over chat-triggered one-shot execution.
- Treat `event log + typed snapshots + job queue + supervisor` as the autonomy core, and place tuning, triage, promotion, and rejection logic in a separate policy layer above it.
