import asyncio
import os
import uuid
from typing import Dict, Set

import pandas as pd
from tqdm import tqdm

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.data import GenData
from poke_env.player import Player


class GameDataManager:
    """Helper class to manage stat information for Gen 9."""

    def __init__(self, gen: int = 9) -> None:
        self.data = GenData.from_gen(gen)

    def get_stat(self, pokemon, stat_name: str) -> int:
        """
        Return a current stat value (battle stat if known, otherwise base stat).

        Falls back to 100 as a neutral default if nothing is available.
        """
        return (
            pokemon.stats.get(stat_name)
            or pokemon.base_stats.get(stat_name)
            or 100
        )


class TFMResearchAgent(Player):
    """
    Version 4 singles heuristic for Gen 9 random battles.

    Logic:
    - Scores available moves using a simple damage estimator.
    - Switches when:
      * we are badly poisoned for a few turns, or
      * our best move is weak AND we are slower.

    For analysis, it also records which moves it used in each battle.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dm = GameDataManager()
        # battle_tag -> set of move ids this agent used in that battle
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

    def choose_move(self, battle):
        me = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        my_status = me.status.name if me.status else "HEALTHY"
        opp_status = opponent.status.name if opponent.status else "HEALTHY"

        # Speed dynamics
        my_speed = self.dm.get_stat(me, "spe") * (0.5 if my_status == "PAR" else 1.0)
        opp_speed = self.dm.get_stat(opponent, "spe") * (0.5 if opp_status == "PAR" else 1.0)

        best_move = None
        max_damage = -1.0
        if battle.available_moves:
            for move in battle.available_moves:
                damage = self._calculate_damage(move, me, opponent, my_status)
                if damage > max_damage:
                    max_damage, best_move = damage, move

        # Strategic switching: tox over time or weak & slower.
        if battle.available_switches:
            if (my_status == "TOX" and me.status_counter > 2) or (
                max_damage < 20 and my_speed < opp_speed
            ):
                return self.create_order(battle.available_switches[0])

        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return self.choose_random_move(battle)

    def _record_used_move(self, battle_tag: str, move_id: str) -> None:
        """Register a used move id for the given battle tag."""
        s = self._used_moves_by_battle.setdefault(battle_tag, set())
        s.add(move_id)

    def _calculate_damage(self, move, attacker, defender, status: str) -> float:
        """
        Simple damage estimator using:
        - physical/special split,
        - burn penalty for physical moves,
        - STAB and type effectiveness.
        """
        if move.base_power <= 1:
            return 0.0
        if move.category.name == "PHYSICAL":
            atk = self.dm.get_stat(attacker, "atk") * (0.5 if status == "BRN" else 1.0)
            defe = self.dm.get_stat(defender, "def")
        else:
            atk = self.dm.get_stat(attacker, "spa")
            defe = self.dm.get_stat(defender, "spd")
        dmg = (atk / defe) * move.base_power * defender.damage_multiplier(move)
        if move.type in attacker.types:
            dmg *= 1.5
        return float(dmg)


async def main() -> None:
    """
    Run a large self-play experiment for the v4 heuristic.

    Produces a CSV with:
    - outcome and length,
    - team compositions,
    - fainted counts,
    - moves used by v4 in each battle.
    """
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_expert_singles_v4_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMResearchAgent(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"V4_A_{run_id}", None),
    )

    opponent = TFMResearchAgent(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"V4_B_{run_id}", None),
    )

    print(f"🚀 Starting {TOTAL_GAMES} games for v4 | Exporting to: {csv_path}")

    with tqdm(total=TOTAL_GAMES, desc="Simulating Battles (v4)", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        for _ in range(batches):
            await player.battle_against(opponent, n_battles=BATCH_SIZE)

            extracted_data = []
            for bid, b in player.battles.items():
                if not b.finished:
                    continue

                if b.won:
                    winner_name = player.username
                elif b.lost:
                    winner_name = opponent.username
                else:
                    winner_name = "DRAW"

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

    print(f"\n✅ Simulation Complete! v4 data saved at {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())