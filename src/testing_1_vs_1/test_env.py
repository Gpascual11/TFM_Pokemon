import asyncio
import logging
from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer


class TFMLoggingPlayer(RandomPlayer):
    """
    A custom agent that extends the RandomPlayer functionality.
    This class serves as a foundation for inspecting the battle state and
    logging the agent's decision-making process.
    """

    def choose_move(self, battle):
        """
        The main decision-making method. Executes at every turn.

        :param battle: The AbstractBattle object containing the full game state.
        :return: A move or switch choice.
        """
        # 1. Extract relevant information from the current state
        me = battle.active_pokemon
        opponent = battle.opponent_active_pokemon

        # 2. Print the context of the turn to the terminal
        print(f"\n" + "=" * 40)
        print(f"--- Turn: {battle.turn} ---")

        # Display Player and Opponent stats
        print(f"PLAYER:   {me.species} ({int(me.current_hp_fraction * 100)}% HP)")
        print(f"          Types: {me.type_1}{', ' + str(me.type_2) if me.type_2 else ''}")

        print(f"OPPONENT: {opponent.species} ({int(opponent.current_hp_fraction * 100)}% HP)")
        print(f"          Types: {opponent.type_1}{', ' + str(opponent.type_2) if opponent.type_2 else ''}")

        # 3. List available moves with their base power
        if battle.available_moves:
            moves_info = [f"{m.id} (Pwr: {m.base_power})" for m in battle.available_moves]
            print(f"Available Moves: {', '.join(moves_info)}")

        # 4. List possible switches
        if battle.available_switches:
            switches_info = [p.species for p in battle.available_switches]
            print(f"Possible Switches: {', '.join(switches_info)}")

        # 5. Call the parent method (Random) to pick an action
        choice = super().choose_move(battle)

        # Log the final choice made by the agent
        print(f">> DECISION: {choice}")
        print("=" * 40)

        return choice


async def main():
    """
    Main function to configure the server, instantiate agents,
    and run the battle simulation.
    """
    print("Configuring the TFM simulation environment...")

    # Local Pokémon Showdown Server configuration
    # Using ws:// protocol for WebSockets and auth=None for offline mode
    custom_config = ServerConfiguration(
        "ws://127.0.0.1:8000/showdown/websocket",
        None
    )

    # Instantiate players using the logging-enabled class
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
        # Run a single battle
        await player_1.battle_against(player_2, n_battles=1)

        # Final session summary
        print("\n" + "#" * 40)
        print("SESSION SUMMARY")
        print(f"Battles played: 1")
        print(f"Wins for {player_1.username}: {player_1.n_won_battles}")
        print(f"Wins for {player_2.username}: {player_2.n_won_battles}")
        print("#" * 40 + "\n")

    except Exception as e:
        print(f"A critical error occurred during simulation: {e}")


if __name__ == "__main__":
    # Start the asynchronous event loop
    asyncio.run(main())