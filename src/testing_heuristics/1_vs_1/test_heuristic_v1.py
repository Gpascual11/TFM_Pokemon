"""Simple baseline heuristic for singles: pick the move with max damage."""

import asyncio
import uuid

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import Player, RandomPlayer


class MaxDamagePlayer(Player):
    """
    Singles heuristic that always selects the move with highest estimated damage.

    Damage is approximated using:
    - base power,
    - type effectiveness,
    - STAB (same-type attack bonus).
    """

    def choose_move(self, battle):
        """
        Choose the move that maximizes the simple damage score, if available.

        :param battle: Current battle state.
        :return: Battle order for the chosen move, or a random move if none.
        """
        if battle.available_moves:
            best_move = max(
                battle.available_moves,
                key=lambda move: self._calculate_score(move, battle),
            )
            return self.create_order(best_move)
        return self.choose_random_move(battle)

    def _calculate_score(self, move, battle) -> float:
        """
        Compute a simple damage-based score for a move.

        :param move: Candidate move.
        :param battle: Current battle state.
        :return: Score proportional to expected damage.
        """
        if move.base_power <= 1:
            return 0.0
        target = battle.opponent_active_pokemon
        effectiveness = target.damage_multiplier(move)
        stab = 1.5 if move.type in battle.active_pokemon.types else 1.0
        return float(move.base_power * effectiveness * stab)


async def main():
    """
    Run a short evaluation: MaxDamagePlayer vs RandomPlayer on random singles.
    """
    run_id = str(uuid.uuid4())[:4]
    print(f"Initializing Session {run_id}: Heuristic vs. Random...")

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    heuristic_agent = MaxDamagePlayer(
        battle_format="gen9randombattle",
        account_configuration=AccountConfiguration(f"Heuristic_{run_id}", None),
        server_configuration=config,
    )

    random_agent = RandomPlayer(
        battle_format="gen9randombattle",
        account_configuration=AccountConfiguration(f"Random_{run_id}", None),
        server_configuration=config,
    )

    print(f"Starting: {heuristic_agent.username} vs {random_agent.username}")

    n_battles = 100
    try:
        await heuristic_agent.battle_against(random_agent, n_battles=n_battles)

        print("\n" + "#" * 40)
        print("EVALUATION SUMMARY")
        print(f"Total Battles: {n_battles}")
        print(f"Heuristic Wins: {heuristic_agent.n_won_battles}")
        print(f"Random Wins:    {random_agent.n_won_battles}")
        print(f"Win Rate:       {(heuristic_agent.n_won_battles / n_battles) * 100:.2f}%")
        print("#" * 40)
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())