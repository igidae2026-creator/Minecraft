# Repo Bundle Upper Bound

This file fixes the large-bundle upper-bound view for the whole repository.

The repository should be read through these seven top-level bundles:

1. `governance_bundle`
2. `autonomy_bundle`
3. `content_bundle`
4. `recovery_audit_bundle`
5. `docs_information_architecture_bundle`
6. `player_experience_bundle`
7. `information_hygiene_bundle`

## Reading

- `governance_bundle`
  MetaOS identity, authority order, and conflict tracking remain intact.
- `autonomy_bundle`
  execution, operational, autonomy, and final threshold surfaces remain closed.
- `content_bundle`
  content depth, evaluation, strategy, soak, and canonical promotion remain active.
- `recovery_audit_bundle`
  repair coupling, audit evidence, and fail-closed recovery remain linked.
- `docs_information_architecture_bundle`
  canonical docs, audit rules, pointers, and reading order stay explicit.
- `player_experience_bundle`
  player-facing completeness is tracked rather than hidden under pure runtime success.
- `information_hygiene_bundle`
  canonical source vs runtime snapshot vs archive candidate separation stays visible.

## Runtime Surfaces

- `runtime_data/autonomy/repo_bundle_summary.yml`
- `runtime_data/repo_bundles/*.json`

The aim is not only to improve one subsystem.
The aim is to keep the whole repository legible, replayable, governable, and extensible under large-bundle reasoning.
