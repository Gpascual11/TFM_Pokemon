import asyncio
import uuid
from tabulate import tabulate
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


class TFMSmartHeuristic(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dm = GameDataManager()

    def choose_move(self, battle):
        me = battle.active_pokemon
        opponent = battle.opponent_active_pokemon

        # 1. Status & Speed Dynamics
        my_status = me.status.name if me.status else "HEALTHY"
        opp_status = opponent.status.name if opponent.status else "HEALTHY"

        # Paralysis speed penalty
        my_speed = self.dm.get_stat(me, "spe") * (0.5 if my_status == "PAR" else 1.0)
        opp_speed_raw = self.dm.get_stat(opponent, "spe")
        opp_speed = opp_speed_raw * (0.5 if opp_status == "PAR" else 1.0)

        # 2. Damage Evaluation (Heuristic Based on Section 3 & 4)
        best_move = None
        max_damage = -1

        if battle.available_moves:
            for move in battle.available_moves:
                damage = self._calculate_heuristic_damage(move, me, opponent, my_status)
                if damage > max_damage:
                    max_damage = damage
                    best_move = move

        # 3. Switching Logic (Strategic Retreat)
        if battle.available_switches:
            # Toxic Reset
            if my_status == "TOX" and me.status_counter > 2:
                return self.create_order(battle.available_switches[0])

            # Type Disadvantage
            if max_damage < 20 and my_speed < opp_speed:
                return self.create_order(battle.available_switches[0])

        return self.create_order(best_move) if best_move else self.choose_random_move(battle)

    def _calculate_heuristic_damage(self, move, attacker, defender, status) -> float:
        if move.base_power <= 1: return 0

        # Physical/Special Split & Burn Penalty
        if move.category.name == "PHYSICAL":
            atk = self.dm.get_stat(attacker, "atk") * (0.5 if status == "BRN" else 1.0)
            defe = self.dm.get_stat(defender, "def")
        else:
            atk = self.dm.get_stat(attacker, "spa")
            defe = self.dm.get_stat(defender, "spd")

        # STAB & Type Effectiveness
        multiplier = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0

        return (atk / defe) * move.base_power * multiplier * stab


async def main():
    run_id = str(uuid.uuid4())[:4]
    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)
    n_battles = 100

    # Increase max_concurrent_battles for performance
    player = TFMSmartHeuristic(
        battle_format="gen9randombattle",
        account_configuration=AccountConfiguration(f"TFM_Logic_{run_id}", None),
        server_configuration=config,
        max_concurrent_battles=10
    )

    opponent = RandomPlayer(
        battle_format="gen9randombattle",
        account_configuration=AccountConfiguration(f"Random_{run_id}", None),
        server_configuration=config,
        max_concurrent_battles=10
    )

    print(f"Starting Session {run_id}: Running {n_battles} battles...")

    # Execute simulation
    await player.battle_against(opponent, n_battles=n_battles)

    # 4. Detailed Data Analysis for TFM
    total_turns = sum(battle.turn for battle in player.battles.values())
    avg_turns = total_turns / n_battles
    win_rate = (player.n_won_battles / n_battles) * 100

    # Summary Table
    results_table = [
        ["Metric", "Value"],
        ["Total Battles", n_battles],
        ["Wins (Heuristic)", player.n_won_battles],
        ["Wins (Random)", opponent.n_won_battles],
        ["Win Rate (%)", f"{win_rate}%"],
        ["Avg. Turns/Battle", f"{avg_turns:.2f}"],
        ["Session ID", run_id]
    ]

    print("\n" + tabulate(results_table, headers="firstrow", tablefmt="grid"))


if __name__ == "__main__":
    asyncio.run(main())