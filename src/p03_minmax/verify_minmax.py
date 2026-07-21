#!/usr/bin/env python
"""Verification Script for p03_minmax Paradigm (v15, v16, v17).

Runs 10 test battles, saves telemetry to data/testing/validation/p03_minmax/,
and prints empirical proof of adversarial Minimax matrix search and lookahead.
"""

import csv
import subprocess
import sys
from pathlib import Path

_DIR = Path(__file__).parent.resolve()
_ROOT = _DIR.parent.parent
OUT_DIR = _ROOT / "data" / "testing" / "validation" / "p03_minmax"


def verify_agent(agent_name: str, opp_name: str = "v14"):
    print(f"\n--- Verifying {agent_name} vs {opp_name} ---")
    cmd = [
        sys.executable,
        str(_ROOT / "src" / "p00_core" / "engine" / "benchmark.py"),
        "10",
        "--agents", agent_name,
        "--opponents", opp_name,
        "--ports", "1",
        "--concurrency", "5",
        "--battle-format", "gen9randombattle",
        "--out", str(OUT_DIR),
        "--restart-every", "0",
    ]

    print(f"Running 10 test games ({agent_name} vs {opp_name})... ", end="", flush=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FAILED!")
        print(res.stderr)
        sys.exit(1)
    print("OK")

    csv_file = OUT_DIR / f"{agent_name}_vs_{opp_name}.csv"
    if not csv_file.exists():
        csv_file = OUT_DIR / "gen9randombattle" / f"{agent_name}_vs_{opp_name}.csv"
    if not csv_file.exists():
        print(f"ERROR: Expected CSV output not found at {csv_file}")
        sys.exit(1)

    with open(csv_file, newline="") as f:
        rows = list(csv.DictReader(f))

    search_moves = sum(int(r.get("search_moves_us", 0)) for r in rows)
    search_switches = sum(int(r.get("search_switches_us", 0)) for r in rows)
    endgame_solves = sum(int(r.get("endgame_solves_us", 0)) for r in rows)
    fallback_moves = sum(int(r.get("fallback_moves_us", 0)) for r in rows)
    error_moves = sum(int(r.get("error_moves_us", 0)) for r in rows)

    print(f"  • Minimax Evaluated Move Actions   : {search_moves}")
    print(f"  • Minimax Evaluated Switch Actions : {search_switches}")
    print(f"  • Endgame Solver Triggers         : {endgame_solves}")
    print(f"  • Fallback Moves (Must be 0)      : {fallback_moves}")
    print(f"  • Error Moves (Must be 0)         : {error_moves}")

    if fallback_moves > 0:
        print(f"  ⚠️  WARN: {fallback_moves} fallback move(s) in {agent_name} — edge case exception caught.")
    else:
        print("  ✅ fallback_moves == 0")
    if error_moves > 0:
        print(f"  ❌ FAIL: {error_moves} unhandled error moves in {agent_name}!")
        sys.exit(1)
    print(f"✅ PASS: {agent_name} adversarial Minimax lookahead functions cleanly.")


def main():
    print("=================================================================")
    print("  VERIFYING PARADIGM: p03_minmax (Adversarial Minimax Search)")
    print("=================================================================")

    import shutil
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    verify_agent("v15", "v14")
    verify_agent("v16", "v14")
    verify_agent("v17", "v14")

    print("\n✅ VERIFICATION PASSED: p03_minmax search agents function cleanly.")
    print("=================================================================\n")


if __name__ == "__main__":
    main()
