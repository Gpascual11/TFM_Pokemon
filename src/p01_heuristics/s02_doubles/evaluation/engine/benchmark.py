#!/usr/bin/env python
"""Unified Parallel Benchmark Runner for Doubles with Resumption and Concurrency."""

import argparse
import logging
import subprocess
import sys
import time
import os
import json
import csv
from pathlib import Path

# Bootstrap path for imports
_DIR = Path(__file__).parent.resolve()
_ROOT = _DIR.parent.parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SRC = _ROOT / "src"
_ENGINE = _DIR

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd
from tabulate import tabulate
from p01_heuristics.s02_doubles.core.factory import AgentFactory

DEFAULT_N = 100
DEFAULT_PORT = 8000
DEFAULT_CONCURRENT_MATCHUPS = 4
DEFAULT_CONCURRENCY_PER_WORKER = 10
DEFAULT_DATA_DIR = _ROOT / "data" / "benchmarks_doubles_unified"

logger = logging.getLogger(__name__)

def get_csv_game_count(csv_path: Path) -> int:
    """Return the number of completed games in the CSV file."""
    if not csv_path.exists():
        return 0
    try:
        with open(csv_path, 'r', newline='') as f:
            reader = csv.reader(f)
            # Count lines minus header
            count = sum(1 for row in reader) - 1
            return max(0, count)
    except Exception:
        return 0

def restart_servers(n_ports: int, start_port: int, roots: Path) -> list:
    print(f"\n♻️  RESTARTING {n_ports} SHOWDOWN SERVERS starting at {start_port}...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        processes = []
        showdown_path = roots / "pokemon-showdown" / "pokemon-showdown"
        for i in range(n_ports):
            port = start_port + i
            p = subprocess.Popen(
                ["node", str(showdown_path), "start", "--port", str(port), "--no-security"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(roots)
            )
            processes.append(p)
        print(f"⏳ Waiting 10 seconds for {n_ports} servers to spin up...")
        time.sleep(10)
        return processes
    except Exception as e:
        print(f"Server restart error: {e}")
        return []

def run_matchup(agent: str, opponent: str, n_battles: int, ports: list[int], concurrency: int, out_dir: Path) -> int:
    out_csv = out_dir / f"{agent}_vs_{opponent}.csv"
    
    existing_count = get_csv_game_count(out_csv)
    if existing_count >= n_battles:
        print(f"⏩ Matchup {agent} vs {opponent} already has {existing_count}/{n_battles} games. Skipping.")
        return existing_count

    remaining = n_battles - existing_count
    print(f"⚔️  Executing {agent} vs {opponent} ({remaining} remaining, {existing_count} already done)...")
    
    n_ports = len(ports)
    battles_per_port = remaining // n_ports
    processes = []
    
    for i, port in enumerate(ports):
        this_n = battles_per_port + (remaining % n_ports if i == 0 else 0)
        if this_n <= 0: continue
        cmd = [
            sys.executable, str(_ENGINE / "worker.py"),
            "--agent", agent,
            "--opponent", opponent,
            "--n-battles", str(this_n),
            "--port", str(port),
            "--concurrency", str(concurrency),
            "--out", str(out_csv)
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_SRC) + ":" + env.get("PYTHONPATH", "")
        
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        processes.append((p, port))

    total_done = 0
    for p, port in processes:
        stdout, stderr = p.communicate()
        if "WORKER_OK:" in stdout:
            try:
                total_done += int(stdout.split("WORKER_OK:")[1].strip())
            except (ValueError, IndexError):
                pass
        if p.returncode != 0:
            print(f"❌ Worker on port {port} failed!")
            if stderr:
                print(f"--- stderr ---\n{stderr}\n--------------")
            
    return existing_count + total_done

def save_checkpoint(stats, out_dir: Path):
    """Save results in a matrix format to checkpoint.json."""
    checkpoint = {}
    for entry in stats:
        agent = entry["Agent"]
        opp = entry["Opponent"]
        wr = float(entry["WR%"])
        if agent not in checkpoint:
            checkpoint[agent] = {}
        checkpoint[agent][opp] = wr
    
    with open(out_dir / "checkpoint.json", 'w') as f:
        json.dump(checkpoint, f, indent=4)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("n_battles", type=int, nargs="?", default=DEFAULT_N)
    parser.add_argument("--agents", nargs="+", help="Primary agents to test")
    parser.add_argument("--opponents", nargs="+", help="Opponents to face")
    parser.add_argument("--ports", type=int, default=DEFAULT_CONCURRENT_MATCHUPS)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY_PER_WORKER)
    parser.add_argument("--start-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out", type=str, default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    ports = [args.start_port + i for i in range(args.ports)]
    
    # Pokechamp heuristic agents (Primary agents to test)
    pokechamp_heuristics = ["abyssal", "one_step", "safe_one_step", "vgc"]
    
    # Internal baseline heuristics
    internals = AgentFactory.available_internal() # v1, v2, v6
    
    # External poke-env baselines
    baselines = ["random", "max_power", "simple_heuristic"]

    agents = args.agents or pokechamp_heuristics
    opponents = args.opponents or (internals + baselines)

    print(f"🚀 Benchmarking {len(agents)} agents vs {len(opponents)} opponents")
    print(f"⚙️  System: {args.ports} workers, each with {args.concurrency} concurrent battles")
    print(f"🎯 Total target: {args.n_battles} games per matchup")

    server_procs = restart_servers(len(ports), args.start_port, _ROOT)
    
    try:
        stats = []
        for agent in agents:
            for opp in opponents:
                if agent == opp: continue
                
                run_matchup(agent, opp, args.n_battles, ports, args.concurrency, out_dir)
                
                csv_path = out_dir / f"{agent}_vs_{opp}.csv"
                if csv_path.exists():
                    df = pd.read_csv(csv_path)
                    if not df.empty and "won" in df.columns:
                        wr = df["won"].mean() * 100
                        stats.append({
                            "Agent": agent, 
                            "Opponent": opp, 
                            "WR%": f"{wr:.1f}", 
                            "Games": len(df)
                        })
                        # Save checkpoint after each matchup
                        save_checkpoint(stats, out_dir)

        print("\n📊 UNIFIED DOUBLES BENCHMARK SUMMARY")
        if stats:
            print(tabulate(stats, headers="keys", tablefmt="github"))
            save_checkpoint(stats, out_dir)
        else:
            print("No results collected.")
        
        print(f"\n✅ All results saved to: {out_dir}")
    finally:
        # Cleanup servers
        print("\n🛑 Shutting down servers...")
        for p in server_procs:
            p.terminate()
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)

if __name__ == "__main__":
    main()
