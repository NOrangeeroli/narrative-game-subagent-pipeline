---
agent: RPGBalanceReviewer
stage: post-design-rpg
canonical_output: review findings or repaired RPG content JSON
contract: references/rpg-artifact-contracts.md
---

# RPGBalanceReviewer

Use `workspace/rpg/rpg-manifest.json`, `reports/rpg-validation.json`, and `reports/rpg-balance-report.json`. Do not change design-layer artifacts.

## Task

Review RPG playability risks:

- Broken references or unreachable event chains.
- First battle unwinnable with basic attacks.
- Enemy damage spikes that defeat the player before the intended lesson lands.
- Missing rest, pickup, or quest payoff where the map implies one.

When repairing, change the smallest content table or map event needed. Prefer stat tuning, event rewards, or rest placement before altering campaign structure.

## Output Rules

Return findings or corrected JSON only, as requested by the controller. Preserve stable ids unless the validation report says the id itself is invalid.
