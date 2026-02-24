"""
Standalone Phase 1 Training Script (Single-threaded).

A simpler alternative to train_parallel.py for environments where
multiprocessing is not desired or needed. Useful for quick verification
of the RL loop.
"""

import logging
from poke_env.player import RandomPlayer
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy

from ..env.pokemon_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper


def main():
    """Main training entry point."""
    print("--- Starting Single-Threaded Phase 1 Training ---")

    # Configure the localhost connection
    server_config = LocalhostServerConfiguration

    # Initialize the random baseline opponent
    opponent = RandomPlayer(
        battle_format="gen9randombattle", server_configuration=server_config
    )

    # Initialize the custom PPO environment
    base_env = PokemonMaskedEnv(
        battle_format="gen9randombattle", server_configuration=server_config
    )

    # Wrap for action masking
    env = PokemonMaskedEnvWrapper(base_env, opponent)

    # Initialize the Maskable PPO Brain
    print("Building MaskablePPO model...")
    model = MaskablePPO(
        MaskableActorCriticPolicy,
        env,
        verbose=1,
        learning_rate=0.0003,
        gamma=0.99,
        tensorboard_log="./ppo_pokemon_tensorboard/",
        n_steps=2048,
    )

    # Training loop
    timesteps = 100_000
    print(f"Training for {timesteps:,} steps...")

    try:
        model.learn(total_timesteps=timesteps)
        model.save("ppo_pokemon_baseline")
        print("Training complete! Model saved as 'ppo_pokemon_baseline.zip'")
    except KeyboardInterrupt:
        print("Training interrupted.")
    finally:
        env.close()


if __name__ == "__main__":
    main()
