#!/usr/bin/env python
"""Parallel LLM Benchmark Orchestrator for Doubles.

This script specializes in running benchmarks for LLM-based agents (Pokellmon, 
Pokechamp LLM). It ensures that LLM thinking and decision logs are captured
for each turn.

It uses the same robust Master-Worker pattern as the general benchmark but 
with settings optimized for LLM resource usage (Ollama backend).
"""

import argparse
import asyncio
import logging
import subprocess
import sys
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

# Configuration
DEFAULT_N = 100
DEFAULT_PORT = 8000
DEFAULT_CONCURRENT_MATCHUPS = 1  # Standard for LLMs to avoid GPU OOM
DEFAULT_DATA_DIR = _ROOT / "data" / "benchmarks_doubles_llm"

# ---------------------------------------------------------------------------
# Server Management
# ---------------------------------------------------------------------------
async def restart_servers_async(n_ports: int) -> None:
    print(f"\n♻️  RESTARTING {n_ports} DOUBLES SHOWDOWN SERVERS...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        await asyncio.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(_ROOT)
        )
        print(f"⏳ Waiting 15 seconds for {n_ports} servers to spin up...")
        await asyncio.sleep(15)
    except Exception as e:
        print(f"❌ Server restart error: {e}")

# ---------------------------------------------------------------------------
# Matchup Logic
# ---------------------------------------------------------------------------
async def run_worker_batch(agent, opponent, n, port, concurrency, out_csv, info):
    print(f"      {info} -> Port {port}: Starting {n} games...", flush=True)
    cmd = [
        sys.executable, str(_ENGINE / "worker.py"),
        "--agent", agent, "--opponent", opponent,
        "--n-battles", str(n), "--port", str(port),
        "--concurrency", str(concurrency), "--out", str(out_csv)
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    
    done = 0
    if proc.returncode == 0:
        for line in stdout.decode().splitlines():
            if "WORKER_OK:" in line:
                done = int(line.split("WORKER_OK:")[1].strip())
        print(f"      {info} -> Port {port}: Finished (Done: {done})", flush=True)
    else:
        print(f"      ❌ {info} -> Port {port} failed: {stderr.decode().strip()}", flush=True)
    return done

async def run_matchup(agent, opponent, target_n, port_queue, concurrency, out_dir):
    out_csv = out_dir / f"{agent}_vs_{opponent}.csv"
    done_prev = 0
    if out_csv.exists():
        try: done_prev = len(pd.read_csv(out_csv))
        except: done_prev = 0
            
    n_run = target_n - done_prev
    if n_run <= 0: return target_n

    print(f"⚔️  LLM Matchup {agent} vs {opponent}: {n_run} missing (Target: {target_n})...")
    
    # For LLMs, we usually run in smaller batches to monitor thinking files
    batch_size = 50 
    tasks = []
    remaining = n_run
    
    async def wrapper(n, idx):
        port = await port_queue.get()
        tmp = out_dir / f"_tmp_llm_{agent}_{opponent}_p{port}_b{idx}.csv"
        try:
            res = await run_worker_batch(agent, opponent, n, port, concurrency, tmp, f"Batch {idx+1}")
            return res, tmp
        finally:
            await port_queue.put(port)

    idx = 0
    while remaining > 0:
        this_n = min(batch_size, remaining)
        tasks.append(wrapper(this_n, idx))
        remaining -= this_n
        idx += 1
        
    results = await asyncio.gather(*tasks)
    frames = []
    total_new = 0
    for d, t in results:
        if d > 0 and t.exists():
            frames.append(pd.read_csv(t))
            t.unlink()
            total_new += d
    
    if frames:
        new_df = pd.concat(frames, ignore_index=True)
        final_df = pd.concat([pd.read_csv(out_csv), new_df], ignore_index=True) if out_csv.exists() else new_df
        final_df.to_csv(out_csv, index=False)
            
    return done_prev + total_new

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("n_battles", type=int, nargs="?", default=20) # Lower default for LLMs
    parser.add_argument("--agents", nargs="+", default=["pokellmon", "pokechamp"])
    parser.add_argument("--opponents", nargs="+", default=["v1", "vgc", "random"])
    parser.add_argument("--ports", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1) # 1 for LLM stability
    parser.add_argument("--out", type=str, default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    port_queue = asyncio.Queue()
    for i in range(args.ports):
        await port_queue.put(8000 + i)
    
    await restart_servers_async(args.ports)
    
    stats = []
    for agent in args.agents:
        for opp in args.opponents:
            if agent == opp: continue
            await run_matchup(agent, opp, args.n_battles, port_queue, args.concurrency, out_dir)
            
            csv_path = out_dir / f"{agent}_vs_{opp}.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                if len(df) > 0:
                    stats.append({"Agent": agent, "Opponent": opp, "WR%": f"{(df['won'].mean()*100):.1f}", "Games": len(df)})

    print("\n📊 LLM DOUBLES BENCHMARK SUMMARY")
    if stats: print(tabulate(stats, headers="keys", tablefmt="github"))
    print(f"\n✅ Logs and CSVs in: {out_dir}")

if __name__ == "__main__":
    try: asyncio.run(main_async())
    except KeyboardInterrupt: sys.exit(130)
