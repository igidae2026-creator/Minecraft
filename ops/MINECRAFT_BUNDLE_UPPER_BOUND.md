# Minecraft Bundle Upper Bound

## Scope

This file fixes the conservative large-bundle view for Minecraft itself, not only for repo structure.

The runtime should evaluate Minecraft through these five large bundles together:

1. `gameplay_progression_bundle`
2. `economy_market_bundle`
3. `social_liveops_bundle`
4. `player_experience_bundle`
5. `anti_cheat_recovery_bundle`
6. `governance_autonomy_bundle`

## Bundle Meaning

### `gameplay_progression_bundle`

- Quest, dungeon, onboarding, and progression loops must create actual playable motion
- Runtime success without gameplay depth is not enough

### `economy_market_bundle`

- Faucet, sink, inflation pressure, and return-player rewards must remain linked
- Economy must be observed as gameplay pressure, not only as config values

### `social_liveops_bundle`

- Events, seasons, social pressure, guild motion, and re-entry loops must stay active
- Player-facing pull matters as much as background automation
- Low completeness should trigger explicit re-entry and guild-cohort live-ops, not only passive rotation

### `player_experience_bundle`

- User-perceived completeness, reward tempo, onboarding friction, and replay pull must stay visible
- Runtime health cannot substitute for player-facing quality
- First-session strength and player-facing soak must both remain governed, not inferred ad hoc

### `anti_cheat_recovery_bundle`

- Sandbox, exploit handling, reconciliation safety, and safe recovery remain coupled
- Growth without safe containment does not count as completeness

### `governance_autonomy_bundle`

- MetaOS identity, final-threshold closure, and large-bundle governance must remain intact
- Minecraft convenience cannot override exploration, lineage, replayability, or append-only truth

## Runtime Reading

- `runtime_data/autonomy/minecraft_bundle_summary.yml`
- `runtime_data/minecraft_bundles/*.json`

## Intent

The target is not only more Minecraft features.
The target is a replayable, governed, player-facing Minecraft operating domain whose large bundles stay legible under autonomous operation.
