import asyncio
import uuid
import pandas as pd
import os
from datetime import datetime
from tqdm import tqdm  # Progress bar library
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import Player, RandomPlayer
from poke_env.data import GenData


class GameDataManager:
    """Helper class to manage Game Theory math and constants."""

    def __init__(self, gen=9):
        self.data = GenData.from_gen(gen)

    def get_stat(self, pokemon, stat_name):
        """Returns exact stat or estimated base stat."""
        return pokemon.stats.get(stat_name) or pokemon.base_stats.get(stat_name) or 100


class TFMResearchAgent(Player):
    """Optimized Heuristic Agent for data collection."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dm = GameDataManager()

    def choose_move(self, battle):
        me = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        my_status = me.status.name if me.status else "HEALTHY"
        opp_status = opponent.status.name if opponent.status else "HEALTHY"

        # Speed Dynamics (Section 5)
        my_speed = self.dm.get_stat(me, "spe") * (0.5 if my_status == "PAR" else 1.0)
        opp_speed = self.dm.get_stat(opponent, "spe") * (0.5 if opp_status == "PAR" else 1.0)

        best_move, max_damage = None, -1
        if battle.available_moves:
            for move in battle.available_moves:
                damage = self._calculate_damage(move, me, opponent, my_status)
                if damage > max_damage:
                    max_damage, best_move = damage, move

        # Strategic Switching (Section 3 & 6)
        if battle.available_switches:
            if (my_status == "TOX" and me.status_counter > 2) or (max_damage < 20 and my_speed < opp_speed):
                return self.create_order(battle.available_switches[0])

        return self.create_order(best_move) if best_move else self.choose_random_move(battle)

    def _calculate_damage(self, move, attacker, defender, status) -> float:
        """Section 4: Physical/Special Split & Multipliers."""
        if move.base_power <= 1: return 0
        if move.category.name == "PHYSICAL":
            atk = self.dm.get_stat(attacker, "atk") * (0.5 if status == "BRN" else 1.0)
            defe = self.dm.get_stat(defender, "def")
        else:
            atk = self.dm.get_stat(attacker, "spa")
            defe = self.dm.get_stat(defender, "spd")
        return (atk / defe) * move.base_power * defender.damage_multiplier(move) * (
            1.5 if move.type in attacker.types else 1.0)


async def main():
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_results_10k_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMResearchAgent(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"Smart_{run_id}", None)
    )

    opponent = RandomPlayer(
        battle_format="gen9randombattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"Rand_{run_id}", None)
    )

    print(f" Starting 10,000 Games | Exporting to: {csv_path}")

    with tqdm(total=TOTAL_GAMES, desc="Simulating Battles", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        for _ in range(batches):
            await player.battle_against(opponent, n_battles=BATCH_SIZE)

            # DATA EXTRACTION (Ultra-Safe Version)
            extracted_data = []
            for bid, b in player.battles.items():
                # We check if the battle is actually over
                if b.finished:
                    # Determine winner name
                    if b.won:
                        winner_name = player.username
                    elif b.lost:
                        winner_name = opponent.username
                    else:
                        winner_name = "DRAW/UNKNOWN"

                    extracted_data.append({
                        "battle_id": bid,
                        "winner": winner_name,
                        "turns": b.turn,
                        "won": 1 if b.won else 0
                    })

            if extracted_data:
                batch_df = pd.DataFrame(extracted_data)
                batch_df.to_csv(csv_path, mode='a', header=not os.path.exists(csv_path), index=False)

            # RAM Management is vital here
            player.reset_battles()
            opponent.reset_battles()
            pbar.update(BATCH_SIZE)

    print(f"\n Simulation Complete! Data saved at {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())