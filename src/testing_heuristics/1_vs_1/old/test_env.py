import asyncio

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer


class TFMLoggingPlayer(RandomPlayer):
    """
    Random policy player that prints the current battle state and its decisions.

    This is mainly used for debugging and understanding what `poke-env` exposes
    at each turn (active Pokémon, HP, types, moves, and switches).
    """

    def choose_move(self, battle):
        """
        Print the current state and delegate the actual choice to RandomPlayer.

        :param battle: Current battle state.
        :return: The chosen move or switch order.
        """
        me = battle.active_pokemon
        opponent = battle.opponent_active_pokemon

        print("\n" + "=" * 40)
        print(f"--- Turn: {battle.turn} ---")

        print(f"PLAYER:   {me.species} ({int(me.current_hp_fraction * 100)}% HP)")
        print(f"          Types: {me.type_1}{', ' + str(me.type_2) if me.type_2 else ''}")

        print(f"OPPONENT: {opponent.species} ({int(opponent.current_hp_fraction * 100)}% HP)")
        print(f"          Types: {opponent.type_1}{', ' + str(opponent.type_2) if opponent.type_2 else ''}")

        if battle.available_moves:
            moves_info = [f"{m.id} (Pwr: {m.base_power})" for m in battle.available_moves]
            print(f"Available Moves: {', '.join(moves_info)}")

        if battle.available_switches:
            switches_info = [p.species for p in battle.available_switches]
            print(f"Possible Switches: {', '.join(switches_info)}")

        choice = super().choose_move(battle)
        print(f">> DECISION: {choice}")
        print("=" * 40)

        return choice


async def main():
    """
    Configure the local server, instantiate two logging players, and run one battle.
    """
    print("Configuring the singles logging environment...")

    custom_config = ServerConfiguration(
        "ws://127.0.0.1:8000/showdown/websocket",
        None,
    )

    player_1 = TFMLoggingPlayer(
        battle_format="gen9randombattle",
        account_configuration=AccountConfiguration("Agent_Alpha", None),
        server_configuration=custom_config,
    )

    player_2 = TFMLoggingPlayer(
        battle_format="gen9randombattle",
        account_configuration=AccountConfiguration("Agent_Beta", None),
        server_configuration=custom_config,
    )

    print(f"Starting simulation: {player_1.username} vs {player_2.username}...")

    try:
        await player_1.battle_against(player_2, n_battles=1)

        print("\n" + "#" * 40)
        print("SESSION SUMMARY")
        print(f"Battles played: 1")
        print(f"Wins for {player_1.username}: {player_1.n_won_battles}")
        print(f"Wins for {player_2.username}: {player_2.n_won_battles}")
        print("#" * 40 + "\n")
    except Exception as e:
        print(f"A critical error occurred during simulation: {e}")


if __name__ == "__main__":
    asyncio.run(main())