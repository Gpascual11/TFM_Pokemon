#!/usr/bin/env python
"""Unified High-Performance Parallel Benchmark Orchestrator for Doubles (2v2).

This script manages large-scale benchmarking of Pokémon Doubles agents. It uses
a Master-Worker pattern where multiple Showdown servers are restarted and 
isolated worker processes are dispatched to run mini-batches of games.

Key features:
- Port-based concurrency (multiple Showdown servers).
- RAM-efficient results collection (tmp CSVs per batch).
- Automatic server cleanup and restart to prevent Showdown memory leaks.
- Supports any agent registerable in `AgentFactory`.
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
import os
import random
from pathlib import Path
import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent.resolve()
_ENGINE = _DIR
_EVAL = _ENGINE.parent
_DOUBLES = _EVAL.parent
_SRC = _DOUBLES.parent.parent
_ROOT = _SRC.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Always inject pokechamp fork FIRST so its poke_env overrides site-packages
_POKECHAMP = _ROOT / "pokechamp"
if _POKECHAMP.exists() and str(_POKECHAMP) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP))

from p01_heuristics.s02_doubles.core.factory import AgentFactory

# Configuration
DEFAULT_N = 100
DEFAULT_PORT = 8000
DEFAULT_CONCURRENT_MATCHUPS = 4
DEFAULT_DATA_DIR = _ROOT / "data" / "benchmarks_doubles_unified"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server Management
# ---------------------------------------------------------------------------
async def restart_servers_async(n_ports: int) -> None:
    """Kills existing Showdown servers and launches new ones."""
    print(f"\n♻️  RESTARTING {n_ports} DOUBLES SHOWDOWN SERVERS...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        await asyncio.sleep(2)
        # Use the specialized launch script
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(_ROOT)
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
    batch_info: str
) -> int:
    """Invokes a worker subprocess to execute a batch of battles."""
    print(f"      {batch_info} -> Port {port}: Starting {n_battles} games...", flush=True)
    
    cmd = [
        sys.executable, str(_ENGINE / "worker.py"),
        "--agent", agent,
        "--opponent", opponent,
        "--n-battles", str(n_battles),
        "--port", str(port),
        "--concurrency", str(concurrency),
        "--out", str(tmp_csv)
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    total_done = 0
    if proc.returncode == 0:
        output = stdout.decode().strip()
        for line in output.splitlines():
            if "WORKER_OK:" in line:
                total_done = int(line.split("WORKER_OK:")[1].strip())
        print(f"      {batch_info} -> Port {port}: Finished (Done: {total_done})", flush=True)
    else:
        err_msg = stderr.decode().strip()
        print(f"      ❌ {batch_info} -> Port {port} failed: {err_msg}", flush=True)
            
    return total_done

async def run_matchup(
    agent: str, 
    opponent: str, 
    target_battles: int, 
    port_queue: asyncio.Queue, 
    concurrency: int, 
    out_dir: Path
) -> int:
    """Orchestrates a specific matchup between two agents."""
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
    battles_per_worker = (n_to_run + n_ports - 1) // n_ports 
    
    tasks = []
    remaining = n_to_run
    
    async def task_wrapper(n, b_idx):
        port = await port_queue.get()
        tmp_csv = out_dir / f"_tmp_doubles_{agent}_{opponent}_p{port}_b{b_idx}.csv"
        try:
            done = await run_worker_batch(
                agent, opponent, n, port, concurrency, tmp_csv, 
                f"[{agent} vs {opponent}] Batch {b_idx+1}"
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
    
    frames = []
    total_new = 0
    for done, tmp_csv in results:
        if done > 0 and tmp_csv.exists():
            frames.append(pd.read_csv(tmp_csv))
            tmp_csv.unlink()
            total_new += done
    
    if frames:
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
    parser.add_argument("--restart-every", type=int, default=10, help="Restart servers every N matchups")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent battles per worker")
    parser.add_argument("--out", type=str, default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    port_queue = asyncio.Queue()
    for i in range(args.ports):
        await port_queue.put(args.start_port + i)
    
    HEURISTICS = [
        "v1", "v2", "v6", 
        "random", "max_power", "simple_heuristic",
        "abyssal", "one_step", "vgc"
    ]
    
    agents = args.agents or HEURISTICS
    opponents = args.opponents or HEURISTICS

    await restart_servers_async(args.ports)
    
    stats = []
    matchup_count = 0
    for agent in agents:
        for opp in opponents:
            if agent == opp: continue
            
            if matchup_count > 0 and matchup_count % args.restart_every == 0:
                await restart_servers_async(args.ports)
            
            total_done = await run_matchup(agent, opp, args.n_battles, port_queue, args.concurrency, out_dir)
            matchup_count += 1
            
            csv_path = out_dir / f"{agent}_vs_{opp}.csv"
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path)
                    if len(df) > 0:
                        wr = df["won"].mean() * 100
                        stats.append({
                            "Agent": agent, 
                            "Opponent": opp, 
                            "WR%": f"{wr:.1f}", 
                            "Games": f"{len(df)}/{args.n_battles}"
                        })
                except Exception:
                    pass

    print("\n📊 UNIFIED DOUBLES BENCHMARK SUMMARY")
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
