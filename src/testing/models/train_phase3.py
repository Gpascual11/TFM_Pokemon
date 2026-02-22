"""
Phase 3: The Gauntlet (Multi-Opponent Training)

This script trains the agent against a mixed pool of opponents:
- RandomPlayer (reinforcing strict basics)
- MaxBasePowerPlayer (reinforcing survival/defense)
- SimpleHeuristicsPlayer (reinforcing tactical adaptation)

It uses the GauntletEnvWrapper which penalizes stalling and 
massively rewards actual victories.
"""

import argparse
import random
import string
import logging
import os
from poke_env.player import RandomPlayer, MaxBasePowerPlayer, SimpleHeuristicsPlayer
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.monitor import Monitor

from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnNoModelImprovement

from rl_env import PokemonMaskedEnv, GauntletEnvWrapper

def make_env(rank: int, port: int, is_eval: bool = False):
    """
    Factory function for generating Phase 3 environments in a SubprocVecEnv.
    
    This function implements "The Gauntlet" curriculum. It assigns a different 
    opponent type to the environment based on its rank (index). This forces the 
    RL agent to train against a mixed pool of opponents simultaneously, preventing
    catastrophic forgetting of basic mechanics while learning advanced tactics.

    Args:
        rank (int): The index of the parallel environment (used for opponent assignment).
        port (int): The localhost port for the Pokémon Showdown server instance.
        is_eval (bool): Flag indicating if this environment is for evaluation.
                        Evaluation environments use a prefix to avoid name collisions
                        and are monitored by the Early Stopping callback.

    Returns:
        Callable: A function that initializes and returns the configured Monitor environment.
    """
    def _init():
        # Generate a unique suffix to prevent account name collisions across parallel processes
        unique_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        
        # Silence ALL loggers in child processes except for CRITICAL errors to prevent console spam
        logging.root.setLevel(logging.ERROR)
        for name in logging.root.manager.loggerDict:
            logging.getLogger(name).setLevel(logging.ERROR)
        
        # Configure the connection to the specific locally-running Showdown server
        server_config = LocalhostServerConfiguration
        server_config = server_config._replace(websocket_url=f"ws://127.0.0.1:{port}/showdown/websocket")

        # Define the Gauntlet Opponent Split
        # Modulo 3 ensures an even distribution of the 3 opponent types across all servers
        prefix = "E" if is_eval else ""
        if rank % 3 == 0:
            opponent_cls = RandomPlayer # Reinforces fundamental game mechanics
            opp_name = f"{prefix}RGntlt{rank}{unique_suffix}"
        elif rank % 3 == 1:
            opponent_cls = MaxBasePowerPlayer # Reinforces defensive survival & type advantage
            opp_name = f"{prefix}MGntlt{rank}{unique_suffix}"
        else:
            opponent_cls = SimpleHeuristicsPlayer # Reinforces complex tactical pivoting
            opp_name = f"{prefix}SGntlt{rank}{unique_suffix}"

        # Initialize the chosen opponent
        opponent = opponent_cls(
            battle_format="gen9randombattle",
            server_configuration=server_config,
            account_configuration=AccountConfiguration(opp_name, None)
        )

        # Initialize the base custom environment (handles action masking and base observations)
        base_env = PokemonMaskedEnv(
            battle_format="gen9randombattle",
            server_configuration=server_config,
            account_configuration1=AccountConfiguration(f"{prefix}GauntBot{rank}{unique_suffix}", None),
        )
        
        # Wrap the environment to apply Phase 3 specific rewards (Stall Penalty & Victory Bonus)
        env = GauntletEnvWrapper(base_env, opponent)
        
        # Wrap in Stable-Baselines Monitor to log episode lengths and rewards to Tensorboard
        return Monitor(env)
    return _init

def main():
    """
    Main execution script for Phase 3 Training.
    
    1. Parses arguments for total timesteps and server ports.
    2. Initializes the training vector environment (The Gauntlet).
    3. (Optional) Initializes the evaluation vector environment for Early Stopping.
    4. Loads the Phase 2 MaskablePPO weights.
    5. Reduces the learning rate (5e-5) to fine-tune without overriding past knowledge.
    6. Executes the learning process and saves the final Phase 3 model.
    """
    parser = argparse.ArgumentParser(description="Train Phase 3 PPO strictly against the Gauntlet.")
    parser.add_argument("--timesteps", type=int, default=2_000_000, help="Total timesteps to train")
    parser.add_argument("--ports", type=int, nargs="+", default=[8000], help="List of server ports")
    parser.add_argument("--eval_ports", type=int, nargs="+", default=[], help="Ports dedicated to the evaluation environments")
    args = parser.parse_args()

    num_envs = len(args.ports)
    print(f"--- Starting Phase 3 Training (The Gauntlet) ---")
    print(f"Servers: {num_envs} | Target Steps: {args.timesteps:,}")

    # Initialize the main Training Environment
    if num_envs == 1:
        vec_env = DummyVecEnv([make_env(0, args.ports[0])])
    else:
        vec_env = SubprocVecEnv([make_env(i, port) for i, port in enumerate(args.ports)])

    eval_env = None
    callbacks = []
    
    # Initialize the Evaluation Environment for Early Stopping
    if args.eval_ports:
        print(f"Setting up Evaluation Environment on {len(args.eval_ports)} ports...")
        eval_env = SubprocVecEnv([make_env(i, port, is_eval=True) for i, port in enumerate(args.eval_ports)])
        
        # Callback: Stop training if the mean reward fails to push a new high for 10 consecutive evaluations
        stop_train_callback = StopTrainingOnNoModelImprovement(max_no_improvement_evals=10, min_evals=5, verbose=1)
        
        # Callback: Trigger an evaluation phase every 50,000 global timesteps
        eval_callback = EvalCallback(eval_env, eval_freq=max(1, 50_000 // num_envs), callback_after_eval=stop_train_callback, verbose=1)
        callbacks.append(eval_callback)
    else:
        print("WARNING: No eval_ports provided. EarlyStoppingCallback is disabled.")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "ppo_pokemon_phase2")
    save_path = os.path.join(script_dir, "ppo_pokemon_phase3")
    
    # Load previous weights to continue the curriculum
    try:
        print(f"Loading Phase 2 weights from {model_path}.zip...")
        model = MaskablePPO.load(model_path, env=vec_env, tensorboard_log="./ppo_pokemon_tensorboard/")
        # Override the loaded learning rate to slow down gradient updates
        model.learning_rate = 5e-5
        print(f"Phase 2 weights loaded. Learning rate overridden to {model.learning_rate}.")
    except FileNotFoundError:
        print("Could not find Phase 2 weights! Phase 3 requires Phase 2 to start.")
        vec_env.close()
        return

    # Execute training loop
    try:
        model.learn(total_timesteps=args.timesteps, reset_num_timesteps=False, callback=callbacks) 
        model.save(save_path)
        print(f"Phase 3 complete. Model saved to {save_path}.zip")
    except KeyboardInterrupt:
        # Gracefully handle Ctrl+C to avoid corrupting the model save
        print("Training interrupted. Saving current progress...")
        model.save(save_path)
    finally:
        # Ensure all parallel ports and child processes are freed
        vec_env.close()
        if eval_env:
            eval_env.close()

if __name__ == "__main__":
    main()
