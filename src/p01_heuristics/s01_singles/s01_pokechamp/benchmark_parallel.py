#!/usr/bin/env python
"""Parallelized Pokechamp Benchmark Orchestrator.

Runs multiple matchups or batches in parallel across multiple Showdown servers.
Each batch is still isolated in a subprocess worker to prevent memory leaks.

Usage::

    uv run python src/p01_heuristics/s01_singles/s01_pokechamp/benchmark_parallel.py 1000 \\
        --ports 4 --workers 4 --pokechamp-agents abyssal safe_one_step
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"

if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles.s01_pokechamp"

from common import prompt_algos
from ..core.factory import HeuristicFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
POKECHAMP_AGENTS = ["random", "max_power", "abyssal", "one_step", "safe_one_step"]
_WORKER_SCRIPT = str(_DIR / "_worker_parallel.py")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Async Helpers
# ---------------------------------------------------------------------------
async def restart_servers_async(n_ports: int) -> None:
    """Kill and restart Showdown servers asynchronously."""
    print("\n♻️  RESTARTING SHOWDOWN SERVERS...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        await asyncio.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"⏳ Waiting 15 seconds for {n_ports} servers to initialize...")
        await asyncio.sleep(15)
    except Exception as e:
        print(f"❌ Failed to restart servers: {e}")

async def run_batch_async(
    pc_agent: str,
    opponent: str,
    n_battles: int,
    port: int,
    battle_format: str,
    out_csv: Path,
) -> int:
    """Run a single batch via _worker_parallel.py and return games completed."""
    cmd = [
        sys.executable,
        _WORKER_SCRIPT,
        "--pc-agent", pc_agent,
        "--opponent", opponent,
        "--n-battles", str(n_battles),
        "--port", str(port),
        "--format", battle_format,
        "--out", str(out_csv),
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        print(f"    ❌ Worker {pc_agent} vs {opponent} on port {port} failed (exit {proc.returncode})")
        err_out = stderr.decode().strip()
        if err_out:
            print(f"       ERROR: {err_out.splitlines()[-1]}")
        return 0
        
    for line in stdout.decode().strip().splitlines():
        if line.startswith("WORKER_OK:"):
            return int(line.split(":")[1])
    return 0

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
async def main_async():
    parser = argparse.ArgumentParser(description="Parallel Pokechamp Benchmark")
    parser.add_argument("total_games", type=int, help="Games per matchup.")
    parser.add_argument("-p", "--ports", type=int, default=1, help="Number of servers (starting from 8000).")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Concurrency limit.")
    parser.add_argument("--pokechamp-agents", nargs="+", default=POKECHAMP_AGENTS)
    parser.add_argument("--battle-format", default="gen9randombattle")
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--restart-every", type=int, default=5, help="Restart servers every N matchups.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--data-dir", default="data/benchmarks_pokechamp_parallel")
    parser.add_argument("--output-csv", default="src/p01_heuristics/s01_singles/s01_pokechamp/results/summary_parallel.csv")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = data_dir / "checkpoint_parallel.json"
    
    ports = [8000 + i for i in range(args.ports)]
    port_queue = asyncio.Queue()
    for p in ports:
        await port_queue.put(p)
    
    semaphore = asyncio.Semaphore(args.workers)
    
    heuristics = ["v1", "v2", "v3", "v4", "v5", "v6"]
    baselines = ["random", "max_power", "simple_heuristic", "abyssal", "one_step", "safe_one_step"]
    opponents = heuristics + baselines
    
    checkpoint_data = {}
    if args.resume and checkpoint_file.exists():
        with open(checkpoint_file) as f:
            checkpoint_data = json.load(f)

    await restart_servers_async(args.ports)

    # Batch tracking
    matchup_batches = {} # match_key -> list of task objects
    
    async def process_batch(pc_agent, opp, n_battles, b_idx, match_key):
        async with semaphore:
            port = await port_queue.get()
            tmp_csv = (data_dir / f"_tmp_{match_key}_p{port}_b{b_idx}.csv").resolve()
            
            print(f"      [Matchup: {match_key}] Starting Batch {b_idx + 1} on Port {port}...", flush=True)
            done = await run_batch_async(
                pc_agent, opp, n_battles, port, args.battle_format, tmp_csv
            )
            print(f"      [Matchup: {match_key}] Batch {b_idx + 1} Finished on Port {port} (Done: {done})", flush=True)
            
            await port_queue.put(port)
            return done, tmp_csv

    for pc_agent in args.pokechamp_agents:
        for opp in opponents:
            match_key = f"{pc_agent}_vs_{opp}"
            if args.resume and match_key in checkpoint_data:
                continue
                
            print(f"📡 Queueing Matchup: {match_key}...")
            
            n_to_run = args.total_games
            b_idx = 0
            match_tasks = []
            
            while n_to_run > 0:
                n = min(args.batch_size, n_to_run)
                match_tasks.append(process_batch(pc_agent, opp, n, b_idx, match_key))
                n_to_run -= n
                b_idx += 1
            
            matchup_batches[match_key] = match_tasks

    # Run all batches
    matchups_since_restart = 0
    for match_key, tasks in matchup_batches.items():
        if matchups_since_restart >= args.restart_every:
            await restart_servers_async(args.ports)
            matchups_since_restart = 0
            
        print(f"⚔️  Executing {match_key} batches...")
        results = await asyncio.gather(*tasks)
        matchups_since_restart += 1
        
        frames = []
        total_done = 0
        for done, tmp_csv in results:
            if done > 0 and tmp_csv.exists():
                frames.append(pd.read_csv(tmp_csv))
                tmp_csv.unlink()
                total_done += done
        
        if frames:
            merged = pd.concat(frames, ignore_index=True)
            csv_path = data_dir / f"pokechamp_{match_key}.csv"
            merged.to_csv(csv_path, index=False)
            
            metrics = {
                "win_rate": (merged["won"].sum() / len(merged)) * 100,
                "avg_turns": merged["turns"].mean(),
                "total_games": len(merged)
            }
            checkpoint_data[match_key] = metrics
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=4)
            print(f"✅ FINALIZED Matchup: {match_key} | {total_done}/{args.total_games} games | {metrics['win_rate']:.1f}% WR")

    print("\n🏁 PARALLEL BENCHMARK COMPLETE!")

if __name__ == "__main__":
    asyncio.run(main_async())
