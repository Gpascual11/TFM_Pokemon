"""
Phase 1: Parallel Reinforcement Learning against Random Opponents.

This script acts as the entry point for the RL curriculum. It trains a 
MaskablePPO model using multiple parallel environments (SubprocVecEnv) to 
achieve higher throughput and faster convergence. 

The primary goal of this phase is for the agent to learn the absolute 
fundamentals of Pokémon battles (e.g., using damaging moves, type matchups) 
by playing against a strictly random baseline (RandomPlayer).
"""

import argparse
import logging
from poke_env.player import RandomPlayer
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.monitor import Monitor

from rl_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper

def make_env(rank: int, port: int):
    """
    Factory function for generating Phase 1 vectorized environments.
    
    This encapsulates the environment creation logic to allow Stable-Baselines3 
    to instantiate parallel instances without pickling issues.
    
    Args:
        rank (int): The index of the environment subprocess.
        port (int): The localhost port for the specific Showdown server instance.
        
    Returns:
        Callable: A function that initializes and returns the configured Monitor environment.
    """
    def _init():
        # Configure connection to a specific localhost port
        server_config = LocalhostServerConfiguration
        server_config = server_config._replace(websocket_url=f"ws://127.0.0.1:{port}/showdown/websocket")

        # Initialize the opponent (Random baseline for Phase 1)
        opponent = RandomPlayer(
            battle_format="gen9randombattle",
            server_configuration=server_config,
        )

        # Initialize the custom PPO environment
        base_env = PokemonMaskedEnv(
            battle_format="gen9randombattle",
            server_configuration=server_config
        )
        
        # Wrap for action masking and monitoring
        env = PokemonMaskedEnvWrapper(base_env, opponent)
        return Monitor(env)

    return _init

def main():
    """
    Main execution script for Phase 1 Training.
    
    Workflow:
    1. Parses arguments for timesteps, server ports, and resuming logic.
    2. Initializes the parallel vector environment (SubprocVecEnv).
    3. Initializes a fresh MaskablePPO model with high-capacity net_arch (256x256)
       and an exploration bonus (ent_coef) to learn basic mechanics quickly.
    4. Executes the learning process and saves the final Phase 1 weights.
    """
    parser = argparse.ArgumentParser(description="Train Phase 1 PPO against RandomPlayer.")
    parser.add_argument("--timesteps", type=int, default=1_000_000, help="Total timesteps to train")
    parser.add_argument("--ports", type=int, nargs="+", default=[8000], help="List of showdown server ports to use")
    parser.add_argument("--resume", action="store_true", help="Resume from ppo_pokemon_baseline.zip if it exists")
    args = parser.parse_args()

    num_envs = len(args.ports)
    print(f"--- Starting Phase 1 Training ---")
    print(f"Servers: {num_envs} | Target Steps: {args.timesteps:,}")

    # Initialize vectorized environment
    if num_envs == 1:
        vec_env = DummyVecEnv([make_env(0, args.ports[0])])
    else:
        vec_env = SubprocVecEnv([make_env(i, port) for i, port in enumerate(args.ports)])

    # Initialize or Load Model
    model_path = "ppo_pokemon_baseline"
    
    if args.resume:
        try:
            print(f"Resuming from {model_path}.zip...")
            model = MaskablePPO.load(model_path, env=vec_env, tensorboard_log="./ppo_pokemon_tensorboard/")
        except FileNotFoundError:
            print("Checkpoint not found. Starting fresh training session.")
            args.resume = False # Reset flag for learn() call

    if not args.resume:
        print("Initializing fresh MaskablePPO model...")
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            vec_env,
            verbose=1,
            learning_rate=3e-4,
            gamma=0.99,
            ent_coef=0.01,          # Encourages broader action exploration
            n_steps=2048,
            policy_kwargs=dict(net_arch=[256, 256]),  # 256x256 > default 64x64
            tensorboard_log="./ppo_pokemon_tensorboard/",
        )

    # Training loop
    try:
        model.learn(total_timesteps=args.timesteps, reset_num_timesteps=not args.resume)
        model.save(model_path)
        print(f"Training complete. Model saved to {model_path}.zip")
    except KeyboardInterrupt:
        print("Training interrupted by user. Saving current weights...")
        model.save(model_path)
    finally:
        vec_env.close()

if __name__ == "__main__":
    main()
