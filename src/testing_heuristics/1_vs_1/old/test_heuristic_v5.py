import asyncio
import os
import uuid
from typing import Dict, Set

import pandas as pd
from tqdm import tqdm

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.data import GenData
from poke_env.player import Player


class TFMExpertHeuristic(Player):
    """
    Expert 1-vs-1 heuristic for Gen 9 random battles.

    This agent:
    - prioritizes immediate KOs using a damage estimator,
    - performs defensive pivots when in danger,
    - scores moves using damage, accuracy and priority,
    - tracks the set of moves it actually used per battle for later analysis.
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize the expert heuristic player.

        :param args: Positional arguments forwarded to `Player`.
        :param kwargs: Keyword arguments forwarded to `Player`.
        """
        super().__init__(*args, **kwargs)
        self.dm = GenData.from_gen(9)
        # battle_tag -> set of move ids used by this agent in that battle
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

    def choose_move(self, battle):
        """
        Select the best action for the current singles battle state.

        Decision order:
        1. Look for guaranteed KOs among priority moves.
        2. If in danger, attempt to pivot into a safer teammate.
        3. Otherwise, evaluate all available moves with a damage-based score.
        """
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # 1. Immediate KO check – prefer higher priority moves that can KO.
        if battle.available_moves:
            sorted_moves = sorted(
                battle.available_moves,
                key=lambda m: m.entry.get("priority", 0),
                reverse=True,
            )
            for move in sorted_moves:
                predicted_dmg = self._estimate_damage(move, me, opp, battle)
                if predicted_dmg >= opp.current_hp:
                    self._record_used_move(battle.battle_tag, move.id)
                    return self.create_order(move)

        # 2. Defensive pivoting when we are in danger or badly poisoned for long.
        my_status = me.status.name if me.status else "HEALTHY"
        if self._is_in_danger(me, opp) or (my_status == "TOX" and me.status_counter > 2):
            best_switch = self._get_best_switch(battle)
            if best_switch:
                return self.create_order(best_switch)

        # 3. Score offensive options; fall back to random if nothing is available.
        best_move = None
        max_score = -1.0

        for move in battle.available_moves or []:
            score = self._score_move(move, me, opp, battle)
            if score > max_score:
                max_score = score
                best_move = move

        if best_move:
            self._record_used_move(battle.battle_tag, best_move.id)
            return self.create_order(best_move)

        return self.choose_random_move(battle)

    def _record_used_move(self, battle_tag: str, move_id: str) -> None:
        """Register a move id as used for the given battle tag."""
        moves = self._used_moves_by_battle.setdefault(battle_tag, set())
        moves.add(move_id)

    def _estimate_damage(self, move, attacker, defender, battle) -> float:
        """
        Estimate expected damage of `move` from `attacker` to `defender`.

        Considers:
        - physical vs. special split and current stats,
        - burn attack penalty,
        - STAB and type effectiveness,
        - basic weather and terrain modifiers.
        """
        if move.base_power <= 1:
            return 0.0

        # Stats & split
        if move.category.name == "PHYSICAL":
            atk = attacker.stats.get("atk") or attacker.base_stats["atk"]
            defe = defender.stats.get("def") or defender.base_stats["def"]
            if attacker.status and attacker.status.name == "BRN":
                atk *= 0.5
        else:
            atk = attacker.stats.get("spa") or attacker.base_stats["spa"]
            defe = defender.stats.get("spd") or defender.base_stats["spd"]

        multiplier = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0

        damage = ((0.5 * move.base_power * (atk / defe) * stab) + 2) * multiplier

        # Weather
        if battle.weather:
            w_name = str(battle.weather).upper()
            if "SUN" in w_name:
                if move.type.name == "FIRE":
                    damage *= 1.5
                if move.type.name == "WATER":
                    damage *= 0.5
            elif "RAIN" in w_name:
                if move.type.name == "WATER":
                    damage *= 1.5
                if move.type.name == "FIRE":
                    damage *= 0.5

        # Terrains
        if battle.fields:
            for field in battle.fields:
                f_name = str(field).upper()
                if "ELECTRIC" in f_name and move.type.name == "ELECTRIC":
                    damage *= 1.3
                elif "GRASSY" in f_name and move.type.name == "GRASS":
                    damage *= 1.3
                elif "PSYCHIC" in f_name and move.type.name == "PSYCHIC":
                    damage *= 1.3

        return float(damage)

    def _is_in_danger(self, me, opp) -> bool:
        """
        Heuristic risk detection using speed and type matchups.

        We consider ourselves "in danger" when:
        - the opponent is faster *and* hits us super-effectively, or
        - our HP fraction is already very low.
        """
        opp_speed = opp.stats.get("spe") or opp.base_stats["spe"]
        my_speed = me.stats.get("spe") or me.base_stats["spe"]

        is_faster = my_speed > opp_speed
        if not is_faster:
            for opp_type in opp.types:
                if me.damage_multiplier(opp_type) >= 2.0:
                    return True
        return me.current_hp_fraction < 0.30

    def _get_best_switch(self, battle):
        """
        Pick a teammate with the lowest worst-type weakness to the opponent.

        Returns:
        - a defensive switch-in if one is clearly safer (worst multiplier <= 1.0),
        - None otherwise.
        """
        best_teammate = None
        min_multiplier = 4.0

        for pokemon in battle.available_switches:
            multiplier = max(
                [pokemon.damage_multiplier(t) for t in battle.opponent_active_pokemon.types]
            )
            if multiplier < min_multiplier:
                min_multiplier = multiplier
                best_teammate = pokemon

        return best_teammate if min_multiplier <= 1.0 else None

    def _score_move(self, move, attacker, defender, battle) -> float:
        """
        Compute a scalar score for a candidate move.

        The score multiplies:
        - estimated damage,
        - effective accuracy (if known),
        and applies a boost to positive-priority moves.
        """
        dmg = self._estimate_damage(move, attacker, defender, battle)
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0

        score = dmg * accuracy

        m_priority = move.entry.get("priority", 0)
        if m_priority > 0:
            score *= 1.5

        return float(score)


async def main() -> None:
    """
    Run a large self-play experiment for the expert singles heuristic.

    Produces a CSV with:
    - battle outcome and length,
    - team compositions (us / opponent),
    - fainted counts,
    - the set of distinct moves used by the expert in each battle.
    """
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_expert_singles_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMExpertHeuristic(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"Expert_A_{run_id}", None),
    )

    opponent = TFMExpertHeuristic(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"Expert_B_{run_id}", None),
    )

    print(f"🚀 Iniciando Simulación Experta (Singles): {TOTAL_GAMES} partidas")
    print(f"📄 Archivo de salida: {csv_path}")

    with tqdm(total=TOTAL_GAMES, desc="Simulando Batallas", unit="game") as pbar:
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

                team_us = "|".join(
                    sorted({str(mon.species) for mon in b.team.values()})
                )
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

    print(f"\n✅ Simulación Finalizada. Datos en {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())