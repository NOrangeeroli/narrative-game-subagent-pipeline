#!/usr/bin/env python3
"""Run a deterministic first-pass balance check for compiled RPG manifests."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from pipeline_lib import Json, as_list, load_optional_json, path_for, write_json


def stats_for(entity: Json) -> Json:
    stats = entity.get("stats") if isinstance(entity.get("stats"), dict) else entity
    return {
        "hp": float(stats.get("hp") or stats.get("max_hp") or 1),
        "attack": float(stats.get("attack") or stats.get("atk") or 1),
        "defense": float(stats.get("defense") or stats.get("def") or 0),
        "speed": float(stats.get("speed") or 1),
    }


def by_id(items: Any) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for item in as_list(items):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            result[item["id"]] = item
    return result


def first_enemy_id_from_event(event: Json, enemies: dict[str, Json], encounters: dict[str, Json]) -> str | None:
    enemy_id = event.get("enemy_id")
    if isinstance(enemy_id, str) and enemy_id in enemies:
        return enemy_id
    encounter_id = event.get("encounter_id")
    encounter = encounters.get(encounter_id) if isinstance(encounter_id, str) else None
    if isinstance(encounter, dict):
        candidates = as_list(encounter.get("enemies") or encounter.get("enemy_ids"))
        for candidate in candidates:
            if isinstance(candidate, str) and candidate in enemies:
                return candidate
            if isinstance(candidate, dict) and isinstance(candidate.get("enemy_id"), str) and candidate["enemy_id"] in enemies:
                return candidate["enemy_id"]
    return next(iter(enemies.keys()), None)


def duel_estimate(actor: Json, enemy: Json) -> Json:
    hero = stats_for(actor)
    foe = stats_for(enemy)
    hero_damage = max(1.0, hero["attack"] - foe["defense"] * 0.5)
    enemy_damage = max(1.0, foe["attack"] - hero["defense"] * 0.5)
    turns_to_win = math.ceil(foe["hp"] / hero_damage)
    turns_to_lose = math.ceil(hero["hp"] / enemy_damage)
    margin = turns_to_lose - turns_to_win
    return {
        "hero_damage_per_turn": round(hero_damage, 2),
        "enemy_damage_per_turn": round(enemy_damage, 2),
        "turns_to_win": turns_to_win,
        "turns_to_lose": turns_to_lose,
        "margin": margin,
        "result": "win" if margin >= 0 else "loss",
    }


def simulate_rpg_balance(run_root: Path) -> Json:
    manifest = load_optional_json(path_for(run_root, "rpg_manifest"))
    if not manifest:
        report = {"status": "skipped", "encounters": [], "warnings": ["Missing workspace/rpg/rpg-manifest.json."]}
        write_json(path_for(run_root, "rpg_balance_report"), report)
        return report

    actors = by_id(manifest.get("actors"))
    enemies = by_id(manifest.get("enemies"))
    encounters = by_id(manifest.get("encounter_tables"))
    party = [actor_id for actor_id in as_list(manifest.get("party")) if isinstance(actor_id, str) and actor_id in actors]
    actor = actors[party[0]] if party else (next(iter(actors.values()), {}) if actors else {})
    results: list[Json] = []
    warnings: list[str] = []

    if not actor:
        warnings.append("No actor available for balance simulation.")
    for game_map in as_list(manifest.get("maps")):
        if not isinstance(game_map, dict):
            continue
        for event in as_list(game_map.get("events")):
            if not isinstance(event, dict) or str(event.get("type") or "") not in ("battle", "encounter"):
                continue
            enemy_id = first_enemy_id_from_event(event, enemies, encounters)
            if not enemy_id:
                results.append({
                    "map_id": game_map.get("id"),
                    "event_id": event.get("id"),
                    "status": "fail",
                    "reason": "No enemy resolved for battle event.",
                })
                continue
            estimate = duel_estimate(actor, enemies[enemy_id]) if actor else {}
            status = "pass" if estimate.get("result") == "win" else "fail"
            results.append({
                "map_id": game_map.get("id"),
                "event_id": event.get("id"),
                "enemy_id": enemy_id,
                "status": status,
                "estimate": estimate,
            })

    if not results:
        warnings.append("No battle events found; balance simulation had no encounters to test.")
    status = "fail" if any(result.get("status") == "fail" for result in results) else "pass"
    report = {
        "status": status,
        "method": "deterministic_basic_attack_duel",
        "actor_id": actor.get("id") if isinstance(actor, dict) else None,
        "encounters": results,
        "warnings": warnings,
    }
    write_json(path_for(run_root, "rpg_balance_report"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    report = simulate_rpg_balance(Path(args.run_root).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
