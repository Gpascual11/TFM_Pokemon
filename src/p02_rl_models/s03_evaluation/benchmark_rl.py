"""Comprehensive Benchmark Script for RL Models with 4-Server Parallelism and RAM Optimization.

Refactored to mirror the RAM-efficient architecture of the Singles Heuristics benchmark:
1. Distributes total games (e.g. 1000) across 4 parallel Showdown servers (250 each).
2. Uses multiprocessing (spawn) to isolate model inference and environment memory.
3. Automatically manages server lifecycles and provides detailed metrics.
"""

import os
import sys
import asyncio
import pandas as pd
import random
import string
import subprocess
import time
import argparse
import logging
import gc
import multiprocessing as mp
from pathlib import Path
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Package bootstrap (Main Process)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _THIS_DIR.parent.parent  # src directory
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Silence noisy connection logs in main process
logging.getLogger("poke_env").setLevel(logging.ERROR)
logging.getLogger("websockets").setLevel(logging.ERROR)

# Absolute imports for registries
from poke_env.player import RandomPlayer, MaxBasePowerPlayer, SimpleHeuristicsPlayer
from poke_env.ps_client.server_configuration import ServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from sb3_contrib import MaskablePPO

from p02_rl_models.s01_env.pokemon_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper
from p01_heuristics.s01_singles.agents import (
    HeuristicV1,
    HeuristicV2,
    HeuristicV3,
    HeuristicV4,
    HeuristicV5,
    HeuristicV6,
)

# Registry for workers to look up opponent classes
OPPONENT_REGISTRY = {
    "rdm": RandomPlayer,
    "mp": MaxBasePowerPlayer,
    "sh": SimpleHeuristicsPlayer,
    "v1": HeuristicV1,
    "v2": HeuristicV2,
    "v3": HeuristicV3,
    "v4": HeuristicV4,
    "v5": HeuristicV5,
    "v6": HeuristicV6,
}

# ---------------------------------------------------------------------------
# Worker Logic (Runs in separate process)
# ---------------------------------------------------------------------------


class EvaluationPlayer(SimpleHeuristicsPlayer):
    """Simple wrapper to run a PPO model for evaluation."""

    def __init__(self, model, **kwargs):
        super().__init__(**kwargs)
        self.model = model

    def choose_move(self, battle):
        if battle.force_switch or battle._wait:
            return super().choose_move(battle)

        wrapper_env = self.model.env.envs[0].env
        base_env = wrapper_env.env

        obs = base_env.embed_battle(battle)
        action_mask = wrapper_env.action_masks()

        action, _ = self.model.predict(
            obs, action_masks=action_mask, deterministic=True
        )
        return base_env.action_to_order(action, battle)


async def _async_worker_matchup(model_name, model_path, opp_label, port, games, queue):
    """Async inner loop for the worker process."""
    server_config = ServerConfiguration(
        f"ws://localhost:{port}/showdown/websocket",
        "https://play.pokemonshowdown.com/action.php",
    )
    opp_class = OPPONENT_REGISTRY[opp_label]

    def get_name(prefix):
        s = "".join(random.choices(string.ascii_lowercase + string.digits, k=3))
        return f"{prefix}{s}"

    def make_eval_env():
        base_env = PokemonMaskedEnv(
            server_configuration=server_config,
            account_configuration1=AccountConfiguration(get_name("WPP"), None),
        )
        dummy_opponent = RandomPlayer(
            server_configuration=server_config,
            account_configuration=AccountConfiguration(get_name("WD"), None),
        )
        return Monitor(PokemonMaskedEnvWrapper(base_env, dummy_opponent))

    try:
        ppo_vec = DummyVecEnv([make_eval_env])
        model = MaskablePPO.load(model_path, env=ppo_vec)

        player = EvaluationPlayer(
            model=model,
            server_configuration=server_config,
            max_concurrent_battles=10,
            account_configuration=AccountConfiguration(
                get_name(f"E{model_name}"), None
            ),
        )

        opp_player = opp_class(
            server_configuration=server_config,
            max_concurrent_battles=10,
            account_configuration=AccountConfiguration(get_name(f"O{opp_label}"), None),
        )

        await player.battle_against(opp_player, n_battles=games)

        results = []
        for battle_id, battle in player.battles.items():
            results.append(
                {
                    "won": 1 if battle.won else 0,
                    "turns": battle.turn,
                    "fainted_opp": len(
                        [p for p in battle.opponent_team.values() if p.fainted]
                    ),
                    "total_hp_us": sum(
                        [p.current_hp_fraction for p in battle.team.values()]
                    ),
                }
            )

        queue.put(results)
    except Exception as e:
        print(f"❌ Worker on port {port} failed: {e}")
        queue.put(None)


def worker_entry(model_name, model_path, opp_label, port, games, queue):
    """Entry point for the spawned process."""
    # Re-bootstrap path in child if needed (though spawn usually handles basic env)
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

    asyncio.run(
        _async_worker_matchup(model_name, model_path, opp_label, port, games, queue)
    )


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------


def restart_servers(n_ports: int = 4):
    """Kills existing servers and starts fresh ones."""
    print(f"\n♻️  RESTARTING {n_ports} SHOWDOWN SERVERS (RAM Optimization)...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(10)
    except Exception as e:
        print(f"❌ Failed to restart servers: {e}")


def main():
    parser = argparse.ArgumentParser(description="RAM-Optimized Parallel RL Benchmark")
    parser.add_argument("--games", type=int, default=1000, help="Games per matchup")
    parser.add_argument(
        "--ports", type=int, default=4, help="Number of parallel servers"
    )
    args = parser.parse_args()

    mp.set_start_method("spawn", force=True)

    print(
        f"🚀 Starting Parallel RL Model Benchmark ({args.games} games, {args.ports} servers)"
    )

    data_dir = Path("/home/gerardpf/TFM/data/models_22_02_26")
    output_dir = Path("/home/gerardpf/TFM/src/p02_rl_models/s03_evaluation/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    model_paths = {
        "B": data_dir / "ppo_pokemon_baseline.zip",
        "P15": data_dir / "ppo_pokemon_phase1_5.zip",
        "P2": data_dir / "ppo_pokemon_phase2.zip",
        "P3": data_dir / "ppo_pokemon_phase3.zip",
    }

    opponents = ["rdm", "mp", "sh", "v1", "v2", "v3", "v4", "v5", "v6"]

    summary_results = []
    restart_servers(args.ports)

    for model_name, path in model_paths.items():
        if not path.exists():
            continue
        print(f"\n📂 Model: {model_name}")

        for opp_label in opponents:
            print(
                f"  ⚔️  Matchup: {model_name} vs {opp_label} ({args.games} games distributed)..."
            )

            # Split games across ports
            per_port = args.games // args.ports

            ctx = mp.get_context("spawn")
            queue = ctx.Queue()
            processes = []

            for i in range(args.ports):
                port = 8000 + i
                p = ctx.Process(
                    target=worker_entry,
                    args=(model_name, str(path), opp_label, port, per_port, queue),
                )
                processes.append(p)
                p.start()

            # Collect results
            matchup_data = []
            for _ in range(args.ports):
                chunk = queue.get()
                if chunk:
                    matchup_data.extend(chunk)

            for p in processes:
                p.join()

            if matchup_data:
                df = pd.DataFrame(matchup_data)
                summary_results.append(
                    {
                        "version": model_name,
                        "opponent": opp_label,
                        "win_rate": (df["won"].sum() / len(df)) * 100,
                        "avg_turns": df["turns"].mean(),
                        "avg_fainted_opp": df["fainted_opp"].mean(),
                        "avg_hp_remaining": df["total_hp_us"].mean(),
                        "total_games": len(df),
                    }
                )
                print(f"    ✅ Result: {summary_results[-1]['win_rate']:.1f}% WR")

            # RAM Clean up between matchups
            del matchup_data
            gc.collect()

            # Periodic server restart every few matchups to clear Node.js RAM
            if len(summary_results) % 3 == 0:
                restart_servers(args.ports)

    # Save to CSV
    df_final = pd.DataFrame(summary_results)
    csv_path = output_dir / "benchmark_rl_summary.csv"
    df_final.to_csv(csv_path, index=False)

    print(f"\n✅ Done! Matrix saved: {csv_path}")

    pivot_wr = df_final.pivot(index="version", columns="opponent", values="win_rate")
    print("\n" + "=" * 80)
    print("🏆 RL MODEL WIN RATE MATRIX (%)")
    print("=" * 80)
    print(tabulate(pivot_wr, headers="keys", tablefmt="psql", floatfmt=".1f"))
    print("=" * 80)


if __name__ == "__main__":
    main()
