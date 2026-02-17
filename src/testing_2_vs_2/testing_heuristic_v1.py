import asyncio
import uuid
import os
import pandas as pd
from tqdm import tqdm
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import Player
from poke_env.data import GenData
from poke_env.player import DoubleBattleOrder


class TFMExpertDoubles(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dm = GenData.from_gen(9)
        self._strict_battle_tracking = False

    def choose_move(self, battle):
        if battle.force_switch:
            orders = []
            selected_indices = set()
            for i, needs_to_switch in enumerate(battle.force_switch):
                if needs_to_switch:
                    switches = battle.available_switches[i] if i < len(battle.available_switches) else []
                    available_choices = [s for s in switches if s not in selected_indices]

                    if available_choices:
                        best_sw = self._get_best_switch_from_list(available_choices, battle)
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
                    if self._estimate_doubles_dmg(move, me, target_opp, battle) >= target_opp.current_hp:
                        score += 1000

                    if score > max_score:
                        max_score = score
                        best_move = move
                        best_target_index = j + 1

            if best_move:
                all_orders.append(self.create_order(best_move, move_target=best_target_index))

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
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_doubles_expert_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMExpertDoubles(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"VGC_A_{run_id}", None)
    )

    opponent = TFMExpertDoubles(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"VGC_B_{run_id}", None)
    )

    print(f"🚀 Iniciando Simulación Experta (Doubles): {TOTAL_GAMES} partidas")

    with tqdm(total=TOTAL_GAMES, desc="Simulando Batallas", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        for _ in range(batches):
            await player.battle_against(opponent, n_battles=BATCH_SIZE)
            extracted_data = []
            for bid, b in player.battles.items():
                if b.finished:
                    winner_name = player.username if b.won else (opponent.username if b.lost else "DRAW")
                    extracted_data.append({
                        "battle_id": bid, "winner": winner_name, "turns": b.turn, "won": 1 if b.won else 0
                    })

            if extracted_data:
                batch_df = pd.DataFrame(extracted_data)
                batch_df.to_csv(csv_path, mode='a', header=not os.path.exists(csv_path), index=False)

            player.reset_battles()
            opponent.reset_battles()
            pbar.update(BATCH_SIZE)


if __name__ == "__main__":
    asyncio.run(main())