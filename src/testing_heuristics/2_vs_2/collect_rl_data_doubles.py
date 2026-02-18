"""
Collect per-turn battle data from v1 and v2 doubles heuristics for RL training.

Runs many games (v1 vs v2, or self-play) and logs at each decision:
- State: active species/types, HP fractions, weather, terrain, remaining mons.
- Action: move_id or switch, target slot.
- Outcome info: estimated damage, type multiplier (so the agent learns
  "this damage is useful against this type"), and battle result when known.

Output CSVs:
- rl_turns_<runid>.csv: one row per turn per slot (state + action + damage info).
- rl_battles_<runid>.csv: one row per battle (teams, winner, turns) for summary.

RL schema (rl_turns_*.csv) — useful for the machine:
- State features: turn, remaining_us, remaining_opp, weather, terrain;
  our_species_0/1, our_types_0/1, our_hp_frac_0/1;
  opp_species_0/1, opp_types_0/1, opp_hp_frac_0/1.
- Action: heuristic (v1|v2), slot (0|1), action_type (move|switch),
  move_id, move_target (1|2), switch_species.
- Damage/type info: estimated_damage (raw damage vs target), type_multiplier
  (e.g. 2.0 = super effective, 0.5 = resisted) — teaches "this damage is
  good against this type".
- Outcome: battle_winner (us|opp|draw), total_turns (filled at battle end).

Usage (server must be running):
  From repo root: uv run python -m src.testing_heuristics.2_vs_2.collect_rl_data_doubles
  From 2_vs_2:     uv run python collect_rl_data_doubles.py
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import DoubleBattleOrder, Player
from tqdm import tqdm

from testing_heuristic_v1 import TFMExpertDoubles as TFMExpertDoublesV1
from testing_heuristic_v2 import TFMExpertDoubles as TFMExpertDoublesV2


# ---------------------------------------------------------------------------
# State and action extraction (shared)
# ---------------------------------------------------------------------------


def _hp_frac(pokemon) -> float:
    if not pokemon or getattr(pokemon, "fainted", False):
        return 0.0
    try:
        frac = getattr(pokemon, "current_hp_fraction", None)
        if frac is not None:
            return float(frac)
        chp = getattr(pokemon, "current_hp", None)
        mhp = getattr(pokemon, "max_hp", None)
        if chp is not None and mhp and mhp > 0:
            return max(0.0, min(1.0, chp / mhp))
    except Exception:
        pass
    return 1.0


def _types_str(pokemon) -> str:
    if not pokemon:
        return ""
    try:
        t = getattr(pokemon, "types", None) or []
        return "|".join(sorted(str(x) for x in t)) if t else ""
    except Exception:
        return ""


def _species_str(pokemon) -> str:
    if not pokemon:
        return ""
    return str(getattr(pokemon, "species", None) or getattr(pokemon, "name", "") or "")


def _extract_battle_state(battle, our_username: str) -> Dict[str, Any]:
    """Build a flat state dict for the current battle turn (for RL features)."""
    our_team = getattr(battle, "team", {})
    opp_team = getattr(battle, "opponent_team", {})
    remaining_us = 6 - sum(1 for m in our_team.values() if getattr(m, "fainted", False))
    remaining_opp = 6 - sum(1 for m in opp_team.values() if getattr(m, "fainted", False))

    actives = getattr(battle, "active_pokemon", None) or []
    opp_actives = getattr(battle, "opponent_active_pokemon", None) or []

    state = {
        "turn": getattr(battle, "turn", 0) or 0,
        "remaining_us": remaining_us,
        "remaining_opp": remaining_opp,
        "weather": str(battle.weather).strip() if getattr(battle, "weather", None) else "",
        "terrain": str(battle.terrain).strip() if getattr(battle, "terrain", None) else "",
    }
    for i in range(2):
        p = actives[i] if i < len(actives) else None
        state[f"our_species_{i}"] = _species_str(p)
        state[f"our_types_{i}"] = _types_str(p)
        state[f"our_hp_frac_{i}"] = _hp_frac(p)
    for i in range(2):
        p = opp_actives[i] if i < len(opp_actives) else None
        state[f"opp_species_{i}"] = _species_str(p)
        state[f"opp_types_{i}"] = _types_str(p)
        state[f"opp_hp_frac_{i}"] = _hp_frac(p)
    return state


def _order_to_orders(order) -> List[Tuple[int, Any, int]]:
    """Return list of (slot_index, order.order (Move or Pokemon), move_target)."""
    out = []
    if order is None:
        return out
    if hasattr(order, "first_order") and hasattr(order, "second_order"):
        for slot, o in enumerate([order.first_order, order.second_order]):
            if o and getattr(o, "order", None) is not None:
                target = getattr(o, "move_target", 0) or 0
                out.append((slot, o.order, target))
    else:
        o = getattr(order, "order", order)
        if o is not None:
            target = getattr(order, "move_target", 0) or 0
            out.append((0, o, target))
    return out


def _is_move(obj) -> bool:
    return hasattr(obj, "base_power") and hasattr(obj, "type") and hasattr(obj, "id")


def _log_rows_for_order(
    battle,
    order,
    heuristic_label: str,
    estimate_damage_fn,
    battle_tag: str,
) -> List[Dict[str, Any]]:
    """
    Given the chosen order and battle state, build one or two turn rows (per slot).
    estimate_damage_fn(move, attacker, defender, battle) -> float.
    """
    state = _extract_battle_state(battle, "")
    rows = []
    actives = getattr(battle, "active_pokemon", None) or []
    opp_actives = getattr(battle, "opponent_active_pokemon", None) or []

    for slot, order_obj, move_target in _order_to_orders(order):
        row = {
            "battle_id": battle_tag,
            "heuristic": heuristic_label,
            **state,
        }
        row["slot"] = slot

        if _is_move(order_obj):
            move = order_obj
            move_id = getattr(move, "id", None) or getattr(move, "name", "") or ""
            row["action_type"] = "move"
            row["move_id"] = move_id
            row["move_target"] = move_target if move_target in (1, 2) else None
            row["switch_species"] = None

            attacker = actives[slot] if slot < len(actives) else None
            opp_idx = (move_target - 1) if move_target in (1, 2) else 0
            defender = opp_actives[opp_idx] if opp_idx < len(opp_actives) else None

            if attacker and defender and not getattr(defender, "fainted", True):
                dmg = estimate_damage_fn(move, attacker, defender, battle)
                row["estimated_damage"] = round(dmg, 2)
                try:
                    mult = defender.damage_multiplier(move)
                    row["type_multiplier"] = float(mult)
                except Exception:
                    row["type_multiplier"] = 1.0
            else:
                row["estimated_damage"] = None
                row["type_multiplier"] = None
        else:
            # Switch
            row["action_type"] = "switch"
            row["move_id"] = None
            row["move_target"] = None
            row["switch_species"] = _species_str(order_obj)
            row["estimated_damage"] = None
            row["type_multiplier"] = None

        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Logging players: wrap v1 and v2 to record each decision
# ---------------------------------------------------------------------------


class LoggingTFMExpertDoublesV1(TFMExpertDoublesV1):
    """V1 heuristic that logs per-turn state/action/damage for RL."""

    def __init__(self, *args, rl_rows_by_battle: Optional[Dict[str, List[dict]]] = None, heuristic_label: str = "v1", **kwargs):
        super().__init__(*args, **kwargs)
        self._rl_rows_by_battle: Dict[str, List[dict]] = rl_rows_by_battle if rl_rows_by_battle is not None else {}
        self._heuristic_label = heuristic_label

    def choose_move(self, battle):
        order = super().choose_move(battle)
        if battle.finished:
            return order
        battle_tag = getattr(battle, "battle_tag", "") or id(battle)
        rows = _log_rows_for_order(
            battle,
            order,
            self._heuristic_label,
            self._estimate_doubles_dmg,
            battle_tag,
        )
        for r in rows:
            self._rl_rows_by_battle.setdefault(battle_tag, []).append(r)
        return order


class LoggingTFMExpertDoublesV2(TFMExpertDoublesV2):
    """V2 heuristic that logs per-turn state/action/damage for RL."""

    def __init__(self, *args, rl_rows_by_battle: Optional[Dict[str, List[dict]]] = None, heuristic_label: str = "v2", **kwargs):
        super().__init__(*args, **kwargs)
        self._rl_rows_by_battle: Dict[str, List[dict]] = rl_rows_by_battle if rl_rows_by_battle is not None else {}
        self._heuristic_label = heuristic_label

    def choose_move(self, battle):
        order = super().choose_move(battle)
        if battle.finished:
            return order
        battle_tag = getattr(battle, "battle_tag", "") or id(battle)
        rows = _log_rows_for_order(
            battle,
            order,
            self._heuristic_label,
            self._estimate_doubles_dmg,
            battle_tag,
        )
        for r in rows:
            self._rl_rows_by_battle.setdefault(battle_tag, []).append(r)
        return order


# ---------------------------------------------------------------------------
# Main: run games and write RL CSVs
# ---------------------------------------------------------------------------


def _flush_battle_rows(
    rl_rows_by_battle: Dict[str, List[dict]],
    player_battles: dict,
    player_won_fn,
    turns_fn,
    out_turns_path: str,
    out_battles_path: str,
    write_header: bool,
) -> bool:
    """
    For each finished battle in player_battles, append battle_winner/total_turns
    to its turn rows, write to out_turns_path, and add one summary row to out_battles_path.
    """
    turn_rows = []
    battle_rows = []
    for bid, b in player_battles.items():
        if not getattr(b, "finished", False):
            continue
        rows = rl_rows_by_battle.pop(bid, [])
        winner = "us" if player_won_fn(b) else ("opp" if b.lost else "draw")
        total_turns = getattr(b, "turn", 0) or 0
        for r in rows:
            r["battle_winner"] = winner
            r["total_turns"] = total_turns
            turn_rows.append(r)

        team_us = "|".join(sorted({str(m.species) for m in b.team.values()}))
        team_opp = "|".join(sorted({str(m.species) for m in b.opponent_team.values()}))
        battle_rows.append({
            "battle_id": bid,
            "winner": winner,
            "turns": total_turns,
            "team_us": team_us,
            "team_opp": team_opp,
        })

    if turn_rows:
        pd.DataFrame(turn_rows).to_csv(
            out_turns_path,
            mode="a",
            header=write_header,
            index=False,
        )
    if battle_rows:
        pd.DataFrame(battle_rows).to_csv(
            out_battles_path,
            mode="a",
            header=write_header,
            index=False,
        )
    return len(turn_rows) > 0 or len(battle_rows) > 0


async def main():
    """Run v1 vs v2 (both sides logged), write per-turn and per-battle CSVs for RL."""
    TOTAL_GAMES = 10_000  # tune for how much data you want
    BATCH_SIZE = 400
    CONCURRENT_BATTLES = 40
    assert TOTAL_GAMES % BATCH_SIZE == 0
    assert BATCH_SIZE % 2 == 0
    per_direction = BATCH_SIZE // 2

    run_id = str(uuid.uuid4())[:6]
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    turns_path = os.path.join(data_dir, f"rl_turns_{run_id}.csv")
    battles_path = os.path.join(data_dir, f"rl_battles_{run_id}.csv")

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    # Shared storage for both players so we merge logs by battle_id
    rl_rows_v1: Dict[str, List[dict]] = {}
    rl_rows_v2: Dict[str, List[dict]] = {}

    v1_player = LoggingTFMExpertDoublesV1(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"RL_V1_{run_id}", None),
        rl_rows_by_battle=rl_rows_v1,
        heuristic_label="v1",
    )
    v2_player = LoggingTFMExpertDoublesV2(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"RL_V2_{run_id}", None),
        rl_rows_by_battle=rl_rows_v2,
        heuristic_label="v2",
    )

    print(f"Collecting RL data: {TOTAL_GAMES} games (v1 vs v2), both sides logged")
    print(f"  Turns CSV: {turns_path}")
    print(f"  Battles CSV: {battles_path}")

    write_header = True
    with tqdm(total=TOTAL_GAMES, desc="RL data collection", unit="game") as pbar:
        for _ in range(TOTAL_GAMES // BATCH_SIZE):
            # v1 as player -> v1's decisions logged in rl_rows_v1
            await v1_player.battle_against(v2_player, n_battles=per_direction)
            _flush_battle_rows(
                rl_rows_v1,
                v1_player.battles,
                lambda b: b.won,
                lambda b: b.turn,
                turns_path,
                battles_path,
                write_header,
            )
            write_header = False
            v1_player.reset_battles()
            v2_player.reset_battles()
            pbar.update(per_direction)

            # v2 as player -> v2's decisions logged in rl_rows_v2
            await v2_player.battle_against(v1_player, n_battles=per_direction)
            _flush_battle_rows(
                rl_rows_v2,
                v2_player.battles,
                lambda b: b.won,
                lambda b: b.turn,
                turns_path,
                battles_path,
                write_header,
            )
            v1_player.reset_battles()
            v2_player.reset_battles()
            pbar.update(per_direction)

    print("Done. Use rl_turns_*.csv for state/action/damage features and rl_battles_*.csv for battle-level summary.")


if __name__ == "__main__":
    asyncio.run(main())
