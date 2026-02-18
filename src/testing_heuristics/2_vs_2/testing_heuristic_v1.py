import asyncio
import os
import uuid
from typing import Dict, Set

import pandas as pd
from tqdm import tqdm

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.data import GenData
from poke_env.player import DoubleBattleOrder, Player


class TFMExpertDoubles(Player):
    """
    Original (v1) doubles heuristic.

    - For each slot, picks the move with highest damage score vs each opponent,
      heavily rewarding guaranteed KOs.
    - Falls back to basic defensive switching when forced.
    - Tracks which move ids it actually uses per battle for richer logging.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dm = GenData.from_gen(9)
        self._strict_battle_tracking = False
        # battle_tag -> set of move ids this agent used in that battle
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

    def _record_used_move(self, battle_tag: str, move_id: str) -> None:
        """Register a move id as used in the given battle."""
        s = self._used_moves_by_battle.setdefault(battle_tag, set())
        s.add(move_id)

    def choose_move(self, battle):
        """
        Decide on a doubles move (or switches) for the current turn.

        - If forced to switch, builds a DoubleBattleOrder of defensive switches.
        - Otherwise, for each active slot, picks the move/target pair with
          highest score and returns a DoubleBattleOrder when possible.
        """
        if battle.force_switch:
            orders = []
            selected_indices = set()
            for i, needs_to_switch in enumerate(battle.force_switch):
                if needs_to_switch:
                    switches = (
                        battle.available_switches[i]
                        if i < len(battle.available_switches)
                        else []
                    )
                    available_choices = [
                        s for s in switches if s not in selected_indices
                    ]

                    if available_choices:
                        best_sw = self._get_best_switch_from_list(
                            available_choices, battle
                        )
                        if best_sw:
                            orders.append(self.create_order(best_sw))
                            selected_indices.add(best_sw)

            if len(orders) > 1:
                return DoubleBattleOrder(orders[0], orders[1])
            return orders[0] if orders else self.choose_random_move(battle)

        all_orders = []
        for i in range(2):
            if i >= len(battle.available_moves) or not battle.available_moves[i]:
                if i < len(battle.available_switches) and battle.available_switches[i]:
                    all_orders.append(self.create_order(battle.available_switches[i][0]))
                continue

            me = battle.active_pokemon[i]
            current_available_moves = battle.available_moves[i]

            best_move = None
            best_target_index = 1
            max_score = -1

            for move in current_available_moves:
                for j, target_opp in enumerate(battle.opponent_active_pokemon):
                    if j > 1 or target_opp is None or target_opp.fainted:
                        continue

                    score = self._score_doubles_move(move, me, target_opp, battle)
                    if (
                        self._estimate_doubles_dmg(move, me, target_opp, battle)
                        >= target_opp.current_hp
                    ):
                        score += 1000

                    if score > max_score:
                        max_score = score
                        best_move = move
                        best_target_index = j + 1

            if best_move:
                self._record_used_move(battle.battle_tag, best_move.id)
                all_orders.append(
                    self.create_order(best_move, move_target=best_target_index)
                )

        if len(all_orders) == 2:
            return DoubleBattleOrder(all_orders[0], all_orders[1])
        elif len(all_orders) == 1:
            return all_orders[0]

        return self.choose_random_move(battle)

    def _get_best_switch_from_list(self, switches, battle):
        """Helper to find the best defensive switch from a specific list."""
        if not switches: return None
        opponents = [p for p in battle.opponent_active_pokemon if p and not p.fainted]
        if not opponents: return switches[0]

        best_teammate = switches[0]
        min_multiplier = 4.0
        for pokemon in switches:
            multiplier = max([pokemon.damage_multiplier(t) for opp in opponents for t in opp.types])
            if multiplier < min_multiplier:
                min_multiplier = multiplier
                best_teammate = pokemon
        return best_teammate

    def _estimate_doubles_dmg(self, move, attacker, defender, battle):
        if move.base_power <= 1: return 0
        if move.category.name == "PHYSICAL":
            atk = attacker.stats.get("atk") or attacker.base_stats["atk"]
            dfe = defender.stats.get("def") or defender.base_stats["def"]
        else:
            atk = attacker.stats.get("spa") or attacker.base_stats["spa"]
            dfe = defender.stats.get("spd") or defender.base_stats["spd"]

        multiplier = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        damage = ((0.5 * move.base_power * (atk / dfe) * stab) + 2) * multiplier

        if move.target in ["allAdjacentFoes", "allAdjacent"]:
            damage *= 0.75

        if battle.weather:
            w = str(battle.weather).upper()
            if "SUN" in w:
                if move.type.name == "FIRE": damage *= 1.5
                if move.type.name == "WATER": damage *= 0.5
            elif "RAIN" in w:
                if move.type.name == "WATER": damage *= 1.5
                if move.type.name == "FIRE": damage *= 0.5
        return damage

    def _score_doubles_move(self, move, attacker, defender, battle):
        dmg = self._estimate_doubles_dmg(move, attacker, defender, battle)
        m_priority = move.entry.get("priority", 0)
        score = dmg * (move.accuracy if isinstance(move.accuracy, float) else 1.0)
        if m_priority > 0: score *= 2.0
        return score


async def main():
    """
    Run a large self-play experiment for the v1 doubles heuristic.

    Produces a CSV with:
    - battle outcome and length,
    - team compositions,
    - fainted counts,
    - moves used by v1 in each battle.
    """
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_doubles_v1_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMExpertDoubles(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"V1_A_{run_id}", None),
    )

    opponent = TFMExpertDoubles(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"V1_B_{run_id}", None),
    )

    print(f"🚀 Iniciando Simulación Experta v1 (Doubles): {TOTAL_GAMES} partidas")

    with tqdm(total=TOTAL_GAMES, desc="Simulando Batallas v1", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        for _ in range(batches):
            await player.battle_against(opponent, n_battles=BATCH_SIZE)
            extracted_data = []
            for bid, b in player.battles.items():
                if not b.finished:
                    continue

                winner_name = (
                    player.username if b.won else (opponent.username if b.lost else "DRAW")
                )

                team_us = "|".join(sorted({str(mon.species) for mon in b.team.values()}))
                team_opp = "|".join(
                    sorted({str(mon.species) for mon in b.opponent_team.values()})
                )

                fainted_us = sum(mon.fainted for mon in b.team.values())
                fainted_opp = sum(mon.fainted for mon in b.opponent_team.values())

                moves_used = "|".join(
                    sorted(player._used_moves_by_battle.get(bid, set()))
                )

                extracted_data.append(
                    {
                        "battle_id": bid,
                        "winner": winner_name,
                        "turns": b.turn,
                        "won": 1 if b.won else 0,
                        "team_us": team_us,
                        "team_opp": team_opp,
                        "fainted_us": fainted_us,
                        "fainted_opp": fainted_opp,
                        "moves_used": moves_used,
                    }
                )

            if extracted_data:
                batch_df = pd.DataFrame(extracted_data)
                batch_df.to_csv(
                    csv_path,
                    mode="a",
                    header=not os.path.exists(csv_path),
                    index=False,
                )

            player.reset_battles()
            opponent.reset_battles()
            pbar.update(BATCH_SIZE)


if __name__ == "__main__":
    asyncio.run(main())