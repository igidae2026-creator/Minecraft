# Content Bundle Upper Bound

## Scope

This document fixes the conservative large-bundle view of Minecraft content completeness.

The runtime should not treat content progress as isolated feature work.
It should evaluate these six large bundles together:

1. `content_depth`
2. `content_evaluation`
3. `portfolio_strategy`
4. `live_data_absorption`
5. `recovery_coupling`
6. `long_soak_canonicalization`

## Bundle Meaning

### `content_depth`

- More than single artifacts
- Quest chains, dungeon variations, season framing, and social loops expand replay depth

### `content_evaluation`

- Content quality is scored through governed signals
- Weak content is held or rejected instead of silently promoted

### `portfolio_strategy`

- The system chooses the next highest-leverage families instead of expanding blindly

### `live_data_absorption`

- Queue pressure, event joins, return-player rewards, economy, and anti-cheat signals affect content direction

### `recovery_coupling`

- Strategy repairs turn into actual queue work
- Content expansion remains fail-closed under repair pressure

### `long_soak_canonicalization`

- Content quality and content strategy are not ephemeral reports
- They must survive soak, become canonical artifacts, and stay replayable

## Runtime Reading

- `content_bundle_summary.yml` is the short runtime surface
- `content_bundles/*.json` is the append-only detailed bundle record

## Current Intent

The target is not merely more content.
The target is a governed content operating surface that can raise player-facing completeness while preserving exploration, lineage, replayability, and append-only truth.

## Current Runtime Focus

- The immediate bundle focus is gameplay progression depth.
- New quest chains, dungeon gauntlets, and seasonal progression arcs should raise real player-facing completeness, not only artifact counts.
- Bundle closure should prefer stable governed soak over circular dependence on the final-threshold output file.
