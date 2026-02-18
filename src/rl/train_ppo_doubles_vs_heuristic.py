from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import numpy as np

from poke_env.ps_client.server_configuration import ServerConfiguration
from poke_env.environment.single_agent_wrapper import SingleAgentWrapper

from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.env_util import make_vec_env

from src.rl.tfm_doubles_env import TFMDoublesEnv


def load_tfm_expert_class():
    """
    Load TFMExpertDoubles from the heuristic file path.

    We load from a file path because the existing folder name `2_vs_2` is not a
    valid python module name for direct imports.
    """
    repo_root = Path(__file__).resolve().parents[2]
    heuristic_path = repo_root / "src" / "testing_heuristics" / "2_vs_2" / "testing_heuristic_v2.py"
    if not heuristic_path.exists():
        raise FileNotFoundError(f"Expected heuristic file at: {heuristic_path}")

    spec = importlib.util.spec_from_file_location("tfm_heuristic_v2", heuristic_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load heuristic module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    if not hasattr(module, "TFMExpertDoubles"):
        raise AttributeError("Heuristic module does not define TFMExpertDoubles")
    return module.TFMExpertDoubles


def main():
    # --- Configuration ---
    BATTLE_FORMAT = "gen9randomdoublesbattle"
    WS_URL = "ws://127.0.0.1:8000/showdown/websocket"

    TOTAL_TIMESTEPS = 200_000

    run_dir = Path("runs") / "ppo_doubles_vs_heuristic_v2"
    models_dir = Path("models")
    run_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # --- Build env (Gen9 Random Doubles) ---
    env_core = TFMDoublesEnv(
        battle_format=BATTLE_FORMAT,
        server_configuration=ServerConfiguration(WS_URL, None),
        # strict=True helps catch illegal actions during dev; set to False for robustness.
        strict=False,
        fake=False,
    )

    # Opponent = your heuristic, but *not* connected to showdown (no listening).
    TFMExpertDoubles = load_tfm_expert_class()
    opponent = TFMExpertDoubles(
        battle_format=BATTLE_FORMAT,
        server_configuration=ServerConfiguration(WS_URL, None),
        start_listening=False,
    )

    gym_env = SingleAgentWrapper(env_core, opponent=opponent)
    gym_env = Monitor(gym_env, filename=str(run_dir / "monitor.csv"))

    # Vectorize (required by stable-baselines3 utilities)
    vec_env = make_vec_env(lambda: gym_env, n_envs=1)

    # --- Train PPO ---
    model = PPO(
        policy="MlpPolicy",
        env=vec_env,
        verbose=1,
        tensorboard_log=str(run_dir),
        n_steps=2048,
        batch_size=64,
        gamma=0.99,
        learning_rate=3e-4,
    )

    model_path = models_dir / "ppo_doubles_vs_heuristic_v2.zip"
    print(f"Training PPO for {TOTAL_TIMESTEPS:,} timesteps...")
    model.learn(total_timesteps=TOTAL_TIMESTEPS, progress_bar=True)
    model.save(str(model_path))
    print(f"Saved model to: {model_path}")

    # Cleanup
    vec_env.close()


if __name__ == "__main__":
    # Stable-baselines3 uses numpy/pytorch; seed for determinism-ish if desired.
    np.random.seed(0)
    os.environ.setdefault("PYTHONHASHSEED", "0")
    main()

