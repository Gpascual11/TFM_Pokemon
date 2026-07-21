#!/usr/bin/env python
"""Verification Script for p01_heuristics Paradigm (v14 vs v1).

Runs 10 test battles, saves telemetry to data/testing/validation/p01_heuristics/,
and prints empirical proof of heuristic rule execution.
"""

import csv
import subprocess
import sys
from pathlib import Path

_DIR = Path(__file__).parent.resolve()
_ROOT = _DIR.parent.parent
OUT_DIR = _ROOT / "data" / "testing" / "validation" / "p01_heuristics"


def main():
    print("=================================================================")
    print("  VERIFYING PARADIGM: p01_heuristics (Heuristic Rules)")
    print("=================================================================")

    import shutil
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(_ROOT / "src" / "p00_core" / "engine" / "benchmark.py"),
        "10",
        "--agents", "v14",
        "--opponents", "v1",
        "--ports", "1",
        "--concurrency", "5",
        "--battle-format", "gen9randombattle",
        "--out", str(OUT_DIR),
        "--restart-every", "0",
    ]

    print("Running 10 test games (v14 vs v1)... ", end="", flush=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FAILED!")
        print(res.stderr)
        sys.exit(1)
    print("OK")

    csv_file = OUT_DIR / "v14_vs_v1.csv"
    if not csv_file.exists():
        csv_file = OUT_DIR / "gen9randombattle" / "v14_vs_v1.csv"
    if not csv_file.exists():
        print(f"ERROR: Expected CSV output not found at {csv_file}")
        sys.exit(1)

    with open(csv_file, newline="") as f:
        rows = list(csv.DictReader(f))

    print("\n--- Empirical Telemetry Proof ---")
    print(f"Total Battles Evaluated: {len(rows)}")

    ko_checks = sum(int(r.get("ko_checks_us", 0)) for r in rows)
    matchup_switches = sum(int(r.get("matchup_switches_us", 0)) for r in rows)
    hazard_sets = sum(int(r.get("hazard_sets_us", 0)) for r in rows)
    setup_uses = sum(int(r.get("setup_uses_us", 0)) for r in rows)
    fallback_moves = sum(int(r.get("fallback_moves_us", 0)) for r in rows)
    error_moves = sum(int(r.get("error_moves_us", 0)) for r in rows)

    print(f"  • Guaranteed KO Checks Performed : {ko_checks}")
    print(f"  • Tactical Matchup Switches       : {matchup_switches}")
    print(f"  • Hazard Placement Events         : {hazard_sets}")
    print(f"  • Setup Sweeper Actions           : {setup_uses}")
    print(f"  • Fallback Moves (Must be 0)     : {fallback_moves}")
    print(f"  • Error Moves (Must be 0)        : {error_moves}")

    assert fallback_moves == 0, "Fallback moves detected in v14!"
    assert error_moves == 0, "Error moves detected in v14!"

    print("\n✅ VERIFICATION PASSED: p01_heuristics rule logic functions cleanly.")
    print("=================================================================\n")


if __name__ == "__main__":
    main()
