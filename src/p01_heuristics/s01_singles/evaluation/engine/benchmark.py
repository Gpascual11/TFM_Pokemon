#!/usr/bin/env python
"""Unified High-Performance Parallel Benchmark Runner.

This orchestrator manages a set of subprocess workers to execute large-scale
Pokémon battle tournaments. It ensures memory safety by isolating
individual matchups in their own processes.

Key Features:
- Resume & Complete: Automatically detects partially finished matchups and completes them.
- Multi-port Showdown server management.
- Dynamic Port Allocation: Spawns workers as ports become available.
- Automatic server restarts to prevent memory bloat.
- Consolidated reporting via terminal and CSV.
"""

import argparse
import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_ENGINE = _DIR
_EVAL = _ENGINE.parent
_SINGLES = _EVAL.parent
_SRC = _SINGLES.parent.parent
_ROOT = _SRC.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from p01_heuristics.s01_singles.core.factory import HeuristicFactory

# Configuration
DEFAULT_N = 100
DEFAULT_PORT = 8000
DEFAULT_CONCURRENT_MATCHUPS = 2
DEFAULT_DATA_DIR = _ROOT / "data" / "1_vs_1" / "benchmarks" / "unified"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Server Management
# ---------------------------------------------------------------------------
async def restart_servers_async(n_ports: int) -> None:
    """Kills existing Showdown servers and launches new ones.

    This ensures that memory bloat in Node.js processes is cleared before starting
    a new set of matchups. Use the `--restart-every` flag to trigger this periodically.

    Args:
        n_ports (int): The number of ports to launch (starting from DEFAULT_PORT).
    """
    print(f"\n♻️  RESTARTING {n_ports} SHOWDOWN SERVERS...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        await asyncio.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(_ROOT),
        )
        print(f"⏳ Waiting 15 seconds for {n_ports} servers to initialize...")
        await asyncio.sleep(15)
    except Exception as e:
        print(f"❌ Server restart error: {e}")


# ---------------------------------------------------------------------------
# Matchup Logic
# ---------------------------------------------------------------------------
async def run_worker_batch(
    agent: str,
    opponent: str,
    n_battles: int,
    port: int,
    concurrency: int,
    tmp_csv: Path,
    batch_info: str,
    battle_format: str = "gen9randombattle",
    player_backend: str = "ollama/qwen3:8b",
    player_prompt_algo: str = "io",
    temperature: float = 0.3,
    log_dir: str = "./battle_log/pokechamp_benchmark",
) -> int:
    """Invokes a worker subprocess to execute a batch of battles.

    Args:
        agent (str): Label of the primary agent.
        opponent (str): Label of the opponent agent.
        n_battles (int): Games to play in this batch.
        port (int): Showdown port to connect to.
        concurrency (int): Maximum simultaneous battles for the worker.
        tmp_csv (Path): Output location for worker-specific data.
        batch_info (str): Descriptive label for logging.

    Returns:
        int: Number of battles successfully completed.
    """
    print(f"      {batch_info} -> Port {port}: Starting {n_battles} games...", flush=True)

    cmd = [
        sys.executable,
        str(_ENGINE / "worker.py"),
        "--agent",
        agent,
        "--opponent",
        opponent,
        "--n-battles",
        str(n_battles),
        "--port",
        str(port),
        "--concurrency",
        str(concurrency),
        "--format",
        battle_format,
        "--player_backend",
        player_backend,
        "--player_prompt_algo",
        player_prompt_algo,
        "--temperature",
        str(temperature),
        "--log-dir",
        log_dir,
        "--out",
        str(tmp_csv),
    ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    total_done = 0
    if proc.returncode == 0:
        output = stdout.decode().strip()
        for line in output.splitlines():
            if "WORKER_OK:" in line:
                total_done = int(line.split("WORKER_OK:")[1].strip())
        print(f"      {batch_info} -> Port {port}: Finished (Done: {total_done})", flush=True)
    else:
        print(f"      ❌ {batch_info} -> Port {port} failed: {stderr.decode().strip()}", flush=True)

    return total_done


async def run_matchup(
    agent: str,
    opponent: str,
    target_battles: int,
    port_queue: asyncio.Queue,
    concurrency: int,
    out_dir: Path,
    battle_format: str,
    player_backend: str,
    player_prompt_algo: str,
    temperature: float,
    log_dir: str,
) -> int:
    """Orchestrates a specific matchup between two agents.

    This function handles the 'Resume & Complete' logic: it checks existing CSVs
    and only runs the remaining number of battles if the target hasn't been reached.

    Args:
        agent (str): Primary agent label.
        opponent (str): Opponent label.
        target_battles (int): Desired total games for this pair.
        port_queue (asyncio.Queue): Available ports for parallel workers.
        concurrency (int): max_concurrent_battles per worker.
        out_dir (Path): Where results are stored.

    Returns:
        int: Total number of games now recorded in the CSV (including previous ones).
    """
    out_csv = out_dir / f"{agent}_vs_{opponent}.csv"

    already_done = 0
    if out_csv.exists():
        try:
            df = pd.read_csv(out_csv)
            already_done = len(df)
        except Exception:
            already_done = 0

    n_to_run = target_battles - already_done
    if n_to_run <= 0:
        print(f"⏩ Matchup {agent} vs {opponent} already finished ({already_done}/{target_battles}). skipping.")
        return target_battles

    print(f"⚔️  Executing {agent} vs {opponent}: {n_to_run} missing games (Total Target: {target_battles})...")

    n_ports = port_queue.qsize()
    # If we have 4 servers, we split the n_to_run into 4 chunks
    battles_per_worker = (n_to_run + n_ports - 1) // n_ports

    tasks = []
    remaining = n_to_run

    # Define a helper to manage port acquisition/release
    async def task_wrapper(n, b_idx):
        port = await port_queue.get()
        # Use a unique temporary file for this specific worker batch
        tmp_csv = out_dir / f"_tmp_{agent}_{opponent}_p{port}_b{b_idx}.csv"
        try:
            done = await run_worker_batch(
                agent,
                opponent,
                n,
                port,
                concurrency,
                tmp_csv,
                f"[{agent} vs {opponent}] Batch {b_idx + 1}",
                battle_format=battle_format,
                player_backend=player_backend,
                player_prompt_algo=player_prompt_algo,
                temperature=temperature,
                log_dir=log_dir,
            )
            return done, tmp_csv
        finally:
            await port_queue.put(port)

    batch_idx = 0
    while remaining > 0:
        this_n = min(battles_per_worker, remaining)
        tasks.append(task_wrapper(this_n, batch_idx))
        remaining -= this_n
        batch_idx += 1

    results = await asyncio.gather(*tasks)

    # Merge all tmp files into the final CSV
    frames = []
    total_new = 0
    for done, tmp_csv in results:
        if done > 0 and tmp_csv.exists():
            frames.append(pd.read_csv(tmp_csv))
            tmp_csv.unlink()  # Delete tmp file after reading
            total_new += done

    if frames:
        # Append new results to the main CSV
        new_df = pd.concat(frames, ignore_index=True)
        if out_csv.exists():
            existing_df = pd.read_csv(out_csv)
            final_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            final_df = new_df
        final_df.to_csv(out_csv, index=False)

    return already_done + total_new


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------
async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("n_battles", type=int, nargs="?", default=DEFAULT_N)
    parser.add_argument("--agents", nargs="+", help="Primary agents to test")
    parser.add_argument("--opponents", nargs="+", help="Opponents to face")
    parser.add_argument("--ports", type=int, default=DEFAULT_CONCURRENT_MATCHUPS)
    parser.add_argument("--start-port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--restart-every",
        type=int,
        default=3,
        help="Restart servers every N matchups (0 disables periodic restarts)",
    )
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent battles per worker")
    parser.add_argument("--out", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--battle-format", type=str, default="gen9randombattle", help="Battle format to play")
    parser.add_argument(
        "--player_backend", type=str, default="ollama/qwen3:8b", help="LLM backend for pokechamp/pokellmon/llm_vgc"
    )
    parser.add_argument(
        "--player_prompt_algo", type=str, default="io", help="Prompt algorithm for pokechamp/pokellmon/llm_vgc"
    )
    parser.add_argument("--temperature", type=float, default=0.3, help="LLM temperature")
    parser.add_argument(
        "--log-dir",
        type=str,
        default="./battle_log/pokechamp_benchmark",
        help="LLM player log directory (pokechamp fork)",
    )
    args = parser.parse_args()

    if args.ports <= 0:
        parser.error("--ports must be a positive integer (>= 1)")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Port Queue
    port_queue = asyncio.Queue()
    for i in range(args.ports):
        await port_queue.put(args.start_port + i)

    # Preferred non-LLM agent list (drawn from factory registries)
    default_internal = HeuristicFactory.available_internal()
    default_baselines = HeuristicFactory.available_baselines()
    DEFAULT_AGENTS = sorted(set(default_internal + default_baselines))

    agents = args.agents or DEFAULT_AGENTS
    opponents = args.opponents or DEFAULT_AGENTS

    await restart_servers_async(args.ports)

    stats = []
    matchup_count = 0
    for agent in agents:
        for opp in opponents:
            if agent == opp:
                continue

            # Periodic Restart
            if args.restart_every > 0 and matchup_count > 0 and matchup_count % args.restart_every == 0:
                await restart_servers_async(args.ports)

            total_done = await run_matchup(
                agent,
                opp,
                args.n_battles,
                port_queue,
                args.concurrency,
                out_dir,
                args.battle_format,
                args.player_backend,
                args.player_prompt_algo,
                args.temperature,
                args.log_dir,
            )
            matchup_count += 1

            # Load results for summary
            csv_path = out_dir / f"{agent}_vs_{opp}.csv"
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path)
                    if len(df) > 0:
                        wr = df["won"].mean() * 100
                        stats.append(
                            {
                                "Agent": agent,
                                "Opponent": opp,
                                "WR%": f"{wr:.1f}",
                                "Games": f"{len(df)}/{args.n_battles}",
                            }
                        )
                except Exception:
                    pass

    print("\n📊 UNIFIED BENCHMARK SUMMARY")
    if stats:
        print(tabulate(stats, headers="keys", tablefmt="github"))

    print(f"\n✅ All results saved to: {out_dir}")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n🛑 Benchmark interrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
