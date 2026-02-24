"""
Phase 1.5: Reinforcement Learning against MaxBasePower Opponents.

This script acts as a curriculum bridge. It resumes training from the Random
baseline weights (Phase 1) and pits the agent against a MaxBasePowerPlayer.

The purpose of this intermediate phase is to force the model to learn
basic defensive switching and prioritization of type advantages. If it stayed
against Random bots, it wouldn't learn to survive strong attacks; if it jumped
straight to Heuristics, it would be overwhelmed. MaxBasePower serves as that
perfect stepping stone.
"""

import argparse
import random
import string
import logging
from poke_env.player import MaxBasePowerPlayer
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.monitor import Monitor

from ..env.pokemon_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper


def make_env(rank: int, port: int):
    """
    Factory function for Phase 1.5 environments.

    Generates unique bot names for each subprocess to prevent Showdown
    account name collisions when running multiple instances in parallel.

    Args:
        rank (int): The index of the parallel environment.
        port (int): The localhost port of the testing Server.

    Returns:
        Callable: A function that initializes and returns the configured Monitor environment.
    """

    def _init():
        unique_suffix = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=5)
        )

        server_config = LocalhostServerConfiguration
        server_config = server_config._replace(
            websocket_url=f"ws://127.0.0.1:{port}/showdown/websocket"
        )

        # Initialize the MaxBasePower opponent
        opponent = MaxBasePowerPlayer(
            battle_format="gen9randombattle",
            server_configuration=server_config,
            account_configuration=AccountConfiguration(
                f"MBP{rank}{unique_suffix}", None
            ),
        )

        # Initialize the PPO environment with a unique bot account
        base_env = PokemonMaskedEnv(
            battle_format="gen9randombattle",
            server_configuration=server_config,
            account_configuration1=AccountConfiguration(
                f"PPOBot{rank}{unique_suffix}", None
            ),
        )

        # Wrap for action masking and monitoring
        env = PokemonMaskedEnvWrapper(base_env, opponent)
        return Monitor(env)

    return _init


def main():
    """
    Main Phase 1.5 training entry point.

    Workflow:
    1. Pareses arguments for timesteps, server ports.
    2. Initializes parallel vector environments configured with MaxBasePowerPlayer.
    3. Loads the previously trained Phase 1 ruleset (`ppo_pokemon_baseline`).
    4. Slightly lowers the learning rate to fine-tune without destroying Phase 1 logic.
    5. Evaluates and saves the specialized Phase 1.5 model.
    """
    parser = argparse.ArgumentParser(
        description="Train Phase 1.5 PPO against MaxBasePowerPlayer."
    )
    parser.add_argument(
        "--timesteps", type=int, default=1_000_000, help="Total timesteps to train"
    )
    parser.add_argument(
        "--ports",
        type=int,
        nargs="+",
        default=[8000],
        help="List of showdown server ports to use",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from current phase weight instead of starting from Phase 1",
    )
    args = parser.parse_args()

    num_envs = len(args.ports)
    print(f"--- Starting Phase 1.5 Training (Curriculum: MaxBasePower) ---")
    print(f"Servers: {num_envs} | Target Steps: {args.timesteps:,}")

    # Initialize vectorized environment
    if num_envs == 1:
        vec_env = DummyVecEnv([make_env(0, args.ports[0])])
    else:
        vec_env = SubprocVecEnv(
            [make_env(i, port) for i, port in enumerate(args.ports)]
        )

    # We load from Phase 1 (baseline) to start, but save as phase1_5
    load_path = "ppo_pokemon_phase1_5" if args.resume else "ppo_pokemon_baseline"
    save_path = "ppo_pokemon_phase1_5"

    try:
        print(f"Loading weights from {load_path}.zip...")
        model = MaskablePPO.load(
            load_path, env=vec_env, tensorboard_log="./ppo_pokemon_tensorboard/"
        )
        # Lower LR slightly from 3e-4 to 2e-4 for this intermediate phase
        model.learning_rate = 2e-4
        print(
            f"Weights loaded successfully. Learning rate set to {model.learning_rate}."
        )
    except FileNotFoundError:
        print(f"Starting model {load_path}.zip not found. Please run Phase 1 first.")
        return

    # Training loop
    try:
        # We use reset_num_timesteps=False to keep the total count continuous in Tensorboard
        model.learn(total_timesteps=args.timesteps, reset_num_timesteps=not args.resume)
        model.save(save_path)
        print(f"Phase 1.5 complete. Model saved to {save_path}.zip")
    except KeyboardInterrupt:
        print("Training interrupted. Saving current progress...")
        model.save(save_path)
    finally:
        vec_env.close()


if __name__ == "__main__":
    main()
