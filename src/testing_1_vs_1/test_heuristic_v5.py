import asyncio
import uuid
import pandas as pd
import os
from datetime import datetime
from tqdm import tqdm
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import Player, RandomPlayer
from poke_env.data import GenData

class TFMExpertHeuristic(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dm = GenData.from_gen(9)

    def choose_move(self, battle):
        me = battle.active_pokemon
        opp = battle.opponent_active_pokemon

        # 1. IMMEDIATE KO CHECK (Section 5: Priority Brackets)
        if battle.available_moves:
            sorted_moves = sorted(
                battle.available_moves,
                key=lambda m: m.entry.get("priority", 0),
                reverse=True
            )
            for move in sorted_moves:
                predicted_dmg = self._estimate_damage(move, me, opp, battle)
                if predicted_dmg >= opp.current_hp:
                    return self.create_order(move)

        # 2. STRATEGIC PIVOTING (Section 3 & 6)
        my_status = me.status.name if me.status else "HEALTHY"
        if self._is_in_danger(me, opp) or (my_status == "TOX" and me.status_counter > 2):
            best_switch = self._get_best_switch(battle)
            if best_switch:
                return self.create_order(best_switch)

        # 3. ADVANCED MOVE SCORING (Section 4, 5, & 9)
        best_move = None
        max_score = -1

        for move in battle.available_moves:
            score = self._score_move(move, me, opp, battle)
            if score > max_score:
                max_score = score
                best_move = move

        return self.create_order(best_move) if best_move else self.choose_random_move(battle)

    def _estimate_damage(self, move, attacker, defender, battle):
        """High-accuracy damage estimation with Field Effects (Section 4 & 9)."""
        if move.base_power <= 1: return 0

        # Stats & Split calculation
        if move.category.name == "PHYSICAL":
            atk = attacker.stats.get("atk") or attacker.base_stats["atk"]
            defe = defender.stats.get("def") or defender.base_stats["def"]
            if attacker.status and attacker.status.name == "BRN":
                atk *= 0.5  # Burn Penalty (Section 6)
        else:
            atk = attacker.stats.get("spa") or attacker.base_stats["spa"]
            defe = defender.stats.get("spd") or defender.base_stats["spd"]

        multiplier = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0

        damage = ((0.5 * move.base_power * (atk / defe) * stab) + 2) * multiplier

        # Weather Effects (Section 9) -
        if battle.weather:
            w_name = str(battle.weather).upper()
            if "SUN" in w_name:
                if move.type.name == "FIRE": damage *= 1.5
                if move.type.name == "WATER": damage *= 0.5
            elif "RAIN" in w_name:
                if move.type.name == "WATER": damage *= 1.5
                if move.type.name == "FIRE": damage *= 0.5

        # Terrain Effects (Section 9) -
        if battle.fields:
            for field in battle.fields:
                f_name = str(field).upper()
                if "ELECTRIC" in f_name and move.type.name == "ELECTRIC":
                    damage *= 1.3
                elif "GRASSY" in f_name and move.type.name == "GRASS":
                    damage *= 1.3
                elif "PSYCHIC" in f_name and move.type.name == "PSYCHIC":
                    damage *= 1.3

        return damage

    def _is_in_danger(self, me, opp):
        """Predicts risk based on Speed and Type Matchups."""
        opp_speed = opp.stats.get("spe") or opp.base_stats["spe"]
        my_speed = me.stats.get("spe") or me.base_stats["spe"]

        is_faster = my_speed > opp_speed
        if not is_faster:
            for opp_type in opp.types:
                if me.damage_multiplier(opp_type) >= 2.0:
                    return True
        return me.current_hp_fraction < 0.3

    def _get_best_switch(self, battle):
        """Finds a teammate to 'absorb' the opponent's hits."""
        best_teammate = None
        min_multiplier = 4.0

        for pokemon in battle.available_switches:
            multiplier = max([pokemon.damage_multiplier(t) for t in battle.opponent_active_pokemon.types])
            if multiplier < min_multiplier:
                min_multiplier = multiplier
                best_teammate = pokemon

        return best_teammate if min_multiplier <= 1.0 else None

    def _score_move(self, move, attacker, defender, battle):
        dmg = self._estimate_damage(move, attacker, defender, battle)
        accuracy = move.accuracy if isinstance(move.accuracy, float) else 1.0

        score = dmg * accuracy

        m_priority = move.entry.get("priority", 0)
        if m_priority > 0:
            score *= 1.5

        return score

async def main():
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_expert_results_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMExpertHeuristic(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"Expert_A_{run_id}", None)
    )

    opponent = TFMExpertHeuristic(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"Expert_B_{run_id}", None)
    )

    print(f" Iniciando Simulación Experta: {TOTAL_GAMES} partidas")
    print(f" Archivo de salida: {csv_path}")

    with tqdm(total=TOTAL_GAMES, desc="Simulando Batallas", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        for _ in range(batches):
            await player.battle_against(opponent, n_battles=BATCH_SIZE)

            extracted_data = []
            for bid, b in player.battles.items():
                if b.finished:
                    winner_name = player.username if b.won else (opponent.username if b.lost else "DRAW")
                    extracted_data.append({
                        "battle_id": bid,
                        "winner": winner_name,
                        "turns": b.turn,
                        "won": 1 if b.won else 0
                    })

            if extracted_data:
                batch_df = pd.DataFrame(extracted_data)
                batch_df.to_csv(csv_path, mode='a', header=not os.path.exists(csv_path), index=False)

            player.reset_battles()
            opponent.reset_battles()
            pbar.update(BATCH_SIZE)

    print(f"\n Simulación Finalizada. Datos en {csv_path}")

if __name__ == "__main__":
    asyncio.run(main())