# RPG Quest Completion Flow Fix

## Problem

The Alice Web RPG could be played through all authored maps and battles, but it could not reach the ending. Runtime quest events only marked objectives as `active`, the campaign final quest id did not match the runtime quest table, and some listed quests had no completion anchor.

## Executed Fix

1. Infer and export a valid `final_quest_id` during RPG manifest compilation.
2. Keep non-final `quest` markers completable by default when no explicit completion source exists.
3. Infer missing quest completion anchors on relevant interactions and final transfers.
4. Let runtime `transfer` events complete quests through `complete_quest_id`.
5. Make runtime final-quest lookup ignore campaign ids that are not present in `quests.json`.

## Process Improvement

The build should treat "can the final quest complete?" as a semantic gate, not only a playtest discovery. `reports/rpg-validation.json` now records inferred quest completion anchors and fails if the final quest still has no completion source.
