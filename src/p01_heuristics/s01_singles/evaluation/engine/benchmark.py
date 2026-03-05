#!/usr/bin/env python
"""Unified High-Performance Parallel Benchmark Runner.

This orchestrator manages a set of subprocess workers to execute large-scale 
Pokémon battle tournaments. It ensures memory safety by isolating 
individual matchups in their own processes.

Key Features:
- Multi-port Showdown server management.
- Automatic server restarts to prevent Node.js memory bloat.
- Checkpoint support (via file presence checks).
- Consolidated reporting via terminal and CSV.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
import os
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

from ...core.factory import AgentFactory

# Configuration
DEFAULT_N = 100
DEFAULT_PORT = 8000
DEFAULT_CONCURRENT_MATCHUPS = 4
DEFAULT_DATA_DIR = _ROOT / "data" / "benchmarks_unified"

logger = logging.getLogger(__name__)

def restart_servers(n_ports: int) -> None:
    """Kill running Showdown servers and launch n_ports instances."""
    print(f"\n♻️  RESTARTING {n_ports} SHOWDOWN SERVERS...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(_ROOT)
        )
        print("⏳ Waiting 15 seconds for startup...")
        time.sleep(15)
    except Exception as e:
        print(f"Server restart error: {e}")

def run_matchup(agent: str, opponent: str, n_battles: int, ports: list[int], out_dir: Path) -> int:
    """Run a single matchup split across multiple ports."""
    out_csv = out_dir / f"{agent}_vs_{opponent}.csv"
    if out_csv.exists():
        print(f"⏩ Matchup {agent} vs {opponent} already exists. Skipping.")
        return n_battles

    print(f"⚔️  Executing {agent} vs {opponent} ({n_battles} games)...")
    
    n_ports = len(ports)
    battles_per_port = n_battles // n_ports
    processes = []
    
    for i, port in enumerate(ports):
        this_n = battles_per_port + (n_battles % n_ports if i == 0 else 0)
        cmd = [
            sys.executable, str(_ENGINE / "worker.py"),
            "--pc-agent", agent,
            "--opponent", opponent,
            "--n-battles", str(this_n),
            "--port", str(port),
            "--out", str(out_csv)
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append((p, port))

    total_done = 0
    for p, port in processes:
        stdout, stderr = p.communicate()
        if "WORKER_OK:" in stdout:
            total_done += int(stdout.split("WORKER_OK:")[1].strip())
        if p.returncode != 0:
            print(f"❌ Worker on port {port} failed: {stderr}")
            
    return total_done

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("n_battles", type=int, nargs="?", default=DEFAULT_N)
    parser.add_argument("--agents", nargs="+", help="Primary agents to test")
    parser.add_argument("--opponents", nargs="+", help="Opponents to face")
    parser.add_argument("--ports", type=int, default=DEFAULT_CONCURRENT_MATCHUPS)
    parser.add_argument("--start-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out", type=str, default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    ports = [args.start_port + i for i in range(args.ports)]
    
    # Defaults if not specified
    agents = args.agents or (AgentFactory.available_internal() + AgentFactory.available_llm())
    opponents = args.opponents or (AgentFactory.available_internal() + AgentFactory.available_baselines())

    restart_servers(len(ports))
    
    stats = []
    for agent in agents:
        for opp in opponents:
            if agent == opp: continue
            
            done = run_matchup(agent, opp, args.n_battles, ports, out_dir)
            
            # Load results for summary
            csv_path = out_dir / f"{agent}_vs_{opp}.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                wr = df["won"].mean() * 100
                stats.append({"Agent": agent, "Opponent": opp, "WR%": f"{wr:.1f}", "Games": len(df)})

    print("\n📊 UNIFIED BENCHMARK SUMMARY")
    if stats:
        print(tabulate(stats, headers="keys", tablefmt="github"))
    
    print(f"\n✅ All results saved to: {out_dir}")

if __name__ == "__main__":
    main()
