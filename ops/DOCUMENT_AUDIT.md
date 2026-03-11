# Document Audit

## Purpose

This file records the current documentation judgment for the repository.
It is not a runtime metric.
It is a structural decision surface for merging, splitting, keeping, or excluding documents.

## Keep As Canonical

- `docs/governance/RULE_CARDS.md`
- `docs/governance/METAOS_CONSTITUTION.md`
- `docs/governance/CONFLICT_LOG.md`
- `ops/AUTONOMY_TARGET.md`
- `ops/RUNBOOK.md`
- `ops/OPS_COMMANDS.md`
- `ops/AUTONOMY_SURFACES.md`
- `ops/RECOVERY_PLAYBOOK.md`
- `ops/CONTENT_BUNDLE_UPPER_BOUND.md`
- `ops/REPO_BUNDLE_UPPER_BOUND.md`
- `ops/MINECRAFT_BUNDLE_UPPER_BOUND.md`
- `ops/CONTENT_COMPLETENESS_KR.md`

Reason:
- These define current operating truth, upper-bound framing, or user-facing completeness criteria.

## Keep As Historical / Framing

- `Genesis.md`
- `EXPLORATION_OS_FRAMING.md`
- `ARTIFACT_LOG.md`
- `FINAL_REPORT.md`
- `FINAL_REPORT_HISTORY.md`

Reason:
- These still matter, but they are framing, history, or legacy release context rather than daily operating documents.

## Exclude From Normal Doc Reasoning

- `.pytest_cache/README.md`
- `.tooling/jdk/legal/**/*.md`

Reason:
- Generated cache or vendor/legal material.
- Useful for packaging/legal provenance, not for runtime/governance/content decisions.

## Merge Judgment

- No immediate hard merge is recommended for governance docs.
  Their separation is useful because `RULE_CARDS`, `CONSTITUTION`, and `CONFLICT_LOG` serve different layers.
- No immediate hard merge is recommended for `AUTONOMY_TARGET.md` and `RUNBOOK.md`.
  One defines the bar; the other defines the operator surface.
- `CONTENT_COMPLETENESS_KR.md` should remain separate from `CONTENT_BUNDLE_UPPER_BOUND.md`.
  One is player-facing perception; the other is internal system bundle structure.

## Split Judgment

- `RUNBOOK.md` has now been split into:
  - `OPS_COMMANDS.md`
  - `AUTONOMY_SURFACES.md`
  - `RECOVERY_PLAYBOOK.md`
- `RUNBOOK.md` should stay as the top-level operating index.
- `FINAL_REPORT.md` may eventually split into:
  - historical release notes
  - retained architecture claims

## Modification Judgment

- Prefer future edits to land in canonical docs first, not in historical docs.
- If a new runtime surface changes operating truth, update `RUNBOOK.md` and the relevant governance or content doc in the same change.
- If a new completeness criterion changes player-facing judgment, update `CONTENT_COMPLETENESS_KR.md` and `CONTENT_BUNDLE_UPPER_BOUND.md` together.
- If a new large-bundle Minecraft criterion changes domain judgment, update `MINECRAFT_BUNDLE_UPPER_BOUND.md` alongside repo/content bundle docs.
- If the active tactical goal changes, update `AUTONOMY_TARGET.md` in the same change that updates the runtime logic.

## Deletion Judgment

- No destructive deletion is recommended yet for canonical or historical docs.
- Generated and vendor docs should remain ignored from normal reasoning, but they do not need content edits.
