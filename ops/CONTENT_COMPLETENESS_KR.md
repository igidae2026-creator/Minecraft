# Minecraft KR User Completeness

## Current Estimate

- Korean game-enjoying general user perceived completeness under the conservative bar: `50-55%`
- Basis date: `2026-03-12`

## What This Percentage Means

This score is not MetaOS operating maturity.
It is the player-facing completeness a Korean user is likely to feel after joining, playing, and deciding whether to keep playing.

## Conservative 100% Bar

- `100%` here includes the kinds of criticism likely to appear later, not only the issues already surfaced now.
- The bar assumes future objections about:
- mismatch between runtime proxies and real fun
- long-soak boredom or drift
- thinness, repetition fatigue, and novelty gap that only appear after repeated sessions
- weak UX polish or emotional payoff
- low content volume or spectacle density even when runtime signals look healthy
  - hidden interaction between new consumers, new faults, and gameplay loops
  - strong operations that still fail to create actual replay desire
- Progress counts only when player-facing quality rises while those likely future objections shrink too.

## Strong Areas

- Stable operating surface with autonomous recovery and fail-closed policy
- Replayable and append-only operating truth
- Governed content pipeline across `quest`, `dungeon`, `event`, `season`, `social`, and `onboarding`
- Content quality scoring and portfolio strategy are now part of the canonical operating surface

## Weak Areas

- Immediate fun and reward tempo at first contact
- Density of player-facing content and variation
- Volume of spectacle and progression span relative to repeated play
- Social competition and cooperation pressure
- Season loop stickiness and return-player pull
- UX polish, presentation, and emotional payoff
- Korean player expectation fit for speed, clarity, and progression feel

## Practical Reading

- MetaOS x Minecraft operational maturity is much higher than player-facing service maturity
- Current system is strong at producing and governing content
- Current game still underdelivers on felt volume, spectacle, and retention pressure

## Next Efficiency Targets

- Raise `social`, `event`, and `onboarding` first
- Increase replay depth without breaking quality gates
- Improve return-player reward pressure and event join rate
- Convert more held content into promoted content without lowering quality
- Reduce `fatigue_gap_score` through novelty bursts, remix social loops, and stronger returner season frames
- Raise `content_volume_score` so perceived completeness does not sit on a thin promoted catalog

## Current Runtime Signals

- `CONTENT_GENERATED=16`
- `CONTENT_PROMOTED=9`
- `CONTENT_HELD=7`
- `CONTENT_FAMILIES=8`
- `CONTENT_AVERAGE_DEPTH_SCORE=1.93`
- `CONTENT_AVERAGE_RETENTION_PROXY=1.53`
- `CONTENT_AVERAGE_QUALITY_SCORE=7.88`
- `CONTENT_VOLUME_SCORE=6.79`
- `PLAYER_EXPERIENCE_PERCENT=50.2`
- `PLAYER_EXPERIENCE_TRUST_PULL=1.0`
- `ENGAGEMENT_FATIGUE_GAP_SCORE=0.44` and is now part of the conservative bar
- `LIVEOPS_BOOST_NOVELTY` should remain available while fatigue stays above the conservative target
- `CONTENT_NEXT_FOCUS=event,quest,dungeon`
