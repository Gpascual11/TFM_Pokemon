"""
Phase 2: Reinforcement Learning against Heuristic Opponents.

This script resumes training from the Phase 1.5 weights (MaxBasePower)
and pits the agent against a smarter `SimpleHeuristicsPlayer`.

The purpose of this phase is to move beyond mere survival and start
developing intelligent tactical countermeasures, aggressive predictions,
and advanced switch logic against an opponent that plays optimally.
"""

import argparse
import random
import string
import logging
from poke_env.player import SimpleHeuristicsPlayer

# Suppress annoying poke_env warnings about invalid orders
logging.getLogger("poke_env").setLevel(logging.ERROR)
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.monitor import Monitor

from ..env.pokemon_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper


def make_env(rank: int, port: int):
    """
    Factory function for Phase 2 environments.

    Creates instances of the `SimpleHeuristicsPlayer` and links them to
    unique parallel PPO agent environments to enable fast vectorized training.

    Args:
        rank (int): The index of the parallel training environment.
        port (int): The localhost port for the specific Showdown server instance.

    Returns:
        Callable: A function that initializes and returns the configured Monitor environment.
    """

    def _init():
        unique_suffix = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=5)
        )

        # Silence ALL loggers in child processes except for CRITICAL errors
        logging.root.setLevel(logging.ERROR)
        for name in logging.root.manager.loggerDict:
            logging.getLogger(name).setLevel(logging.ERROR)

        server_config = LocalhostServerConfiguration
        server_config = server_config._replace(
            websocket_url=f"ws://127.0.0.1:{port}/showdown/websocket"
        )

        # Initialize the smart heuristic opponent
        opponent = SimpleHeuristicsPlayer(
            battle_format="gen9randombattle",
            server_configuration=server_config,
            account_configuration=AccountConfiguration(
                f"SHeur{rank}{unique_suffix}", None
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
    Main Phase 2 training entry point.

    Workflow:
    1. Parses CLI arguments for ports and timesteps.
    2. Constructs parallel Phase 2 heuristic training environments.
    3. Loads Phase 1.5 weights (the previous curriculum step).
    4. Drops the learning rate even further (1.5e-4) to carefully adjust
       weights for heuristic combat without catastrophic forgetting.
    5. Saves weights as the `ppo_pokemon_phase2` model.
    """
    parser = argparse.ArgumentParser(
        description="Train Phase 2 PPO against SimpleHeuristicPlayer."
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
        "--resume", action="store_true", help="Resume from ppo_pokemon_baseline.zip"
    )
    args = parser.parse_args()

    num_envs = len(args.ports)
    print(f"--- Starting Phase 2 Training (Heuristics Curriculum) ---")
    print(f"Servers: {num_envs} | Target Steps: {args.timesteps:,}")

    # Initialize vectorized environment
    if num_envs == 1:
        vec_env = DummyVecEnv([make_env(0, args.ports[0])])
    else:
        vec_env = SubprocVecEnv(
            [make_env(i, port) for i, port in enumerate(args.ports)]
        )

    # Phase 2 always starts from the Phase 1.5 checkpoint (or resumes Phase 2)
    model_path = "ppo_pokemon_phase2" if args.resume else "ppo_pokemon_phase1_5"
    save_path = "ppo_pokemon_phase2"

    try:
        print(f"Loading weights from {model_path}.zip...")
        model = MaskablePPO.load(
            model_path, env=vec_env, tensorboard_log="./ppo_pokemon_tensorboard/"
        )
        # Lower LR prevents catastrophic forgetting of Phase 1 fundamentals
        model.learning_rate = 1.5e-4
        print(
            f"Phase 1 weights loaded. Learning rate overridden to {model.learning_rate}."
        )
    except FileNotFoundError:
        print(
            f"Baseline {model_path}.zip not found. Starting from scratch (not recommended for Phase 2)."
        )
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            vec_env,
            verbose=1,
            learning_rate=1.5e-4,
            ent_coef=0.01,
            n_steps=2048,
            policy_kwargs=dict(net_arch=[256, 256]),
            tensorboard_log="./ppo_pokemon_tensorboard/",
        )

    # Training loop
    try:
        # We use reset_num_timesteps=False to keep the total count continuous in Tensorboard
        model.learn(total_timesteps=args.timesteps, reset_num_timesteps=not args.resume)
        model.save(save_path)
        print(f"Phase 2 complete. Model saved to {save_path}.zip")
    except KeyboardInterrupt:
        print("Training interrupted. Saving current progress...")
        model.save(save_path)
    finally:
        vec_env.close()


if __name__ == "__main__":
    main()
