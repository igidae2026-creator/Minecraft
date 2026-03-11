# Autonomy Surfaces

## Core

- append-only event log
- typed snapshots
- file-backed job queue
- resident supervisor
- policy layer above the core

Core autonomy state lives under `runtime_data/autonomy/core`.

## Control / Lineage

- control state: `runtime_data/autonomy/control/state.yml`
- append-only control lineage: `runtime_data/autonomy/control/lineage.jsonl`
- append-only decisions: `runtime_data/autonomy/decisions`
- pre-mutation backups: `runtime_data/autonomy/backups`

## Supervisor

- heartbeat, state, pid, and logs: `runtime_data/autonomy/supervisor`
- active soak transitions are treated as lineage state, not ad hoc tuning
- while soak is active, policy should prefer bounded observation over new branch creation

## Content Upper-Bound Surfaces

- content quality summary
- content strategy summary
- content soak summary
- content bundle summary
- minecraft strategy summary
- minecraft soak summary
- player experience summary
- player experience soak summary
- canonical artifact registry including:
  - `content_quality_profile`
  - `content_portfolio_strategy`
  - `content_soak_report`
  - `repo_bundle_profile`
  - `minecraft_domain_bundle_profile`
  - `minecraft_domain_strategy`
  - `minecraft_domain_soak_report`
  - `player_experience_profile`
  - `player_experience_soak_report`

## Audit / Governance

- MetaOS governance docs under `docs/governance`
- repo coverage and conflict tracking under `runtime_data/audit`
- `python3 ops/metaos_conformance.py` refreshes the audit surfaces
