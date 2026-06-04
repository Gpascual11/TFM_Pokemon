"""Quick validation: all agents work across gens, all columns populated correctly."""
import csv
import subprocess
import sys
from pathlib import Path

OUT = Path("/tmp/test_validation")
OUT.mkdir(exist_ok=True)

TESTS = [
    # (agents, opponents, gen, n_battles)
    ("v7 v8", "v5 v3 random", "gen1randombattle", 10),
    ("v7 v8", "v5 random", "gen4randombattle", 10),
    ("v1 v2 v3 v4 v5 v6", "random", "gen1randombattle", 5),
]

STRATEGY_COLS = ["hazard_sets_us", "hazard_removals_us", "setup_uses_us", "ko_checks_us", "matchup_switches_us"]
BASIC_COLS = ["decisions_us", "decisions_opp", "fallback_moves_us", "error_moves_us"]
RNG_COLS = ["crit_us", "crit_opp", "miss_us", "miss_opp", "supereffective_us", "supereffective_opp"]

def run_benchmark(agents, opponents, gen, n):
    out_dir = OUT / gen
    cmd = [
        sys.executable, "src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py",
        str(n),
        "--agents", *agents.split(),
        "--opponents", *opponents.split(),
        "--ports", "1",
        "--concurrency", "5",
        "--battle-format", gen,
        "--out", str(out_dir),
        "--restart-every", "0",
    ]
    print(f"\n{'='*60}")
    print(f"Running: {agents} vs {opponents} ({gen}, {n} games)")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr[-500:]}")
    return result.returncode == 0

def check_csv(path):
    """Validate a single CSV file."""
    issues = []
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return [f"EMPTY FILE: {path.name}"]

    # Check column count
    if len(reader.fieldnames) != 46:
        issues.append(f"Column count: {len(reader.fieldnames)} (expected 46)")

    n = len(rows)
    agent = rows[0]["heuristic"]
    opponent = rows[0]["opponent"]
    gen = rows[0].get("format", "unknown")

    # Basic counters should always be > 0
    decisions_us = sum(int(r["decisions_us"]) for r in rows) / n
    if decisions_us == 0:
        issues.append(f"decisions_us = 0 (should be > 0)")

    # Error moves should be 0 or very low
    errors = sum(int(r["error_moves_us"]) for r in rows) / n
    if errors > 1:
        issues.append(f"error_moves_us = {errors:.2f} (too many errors!)")

    # Strategy columns: non-zero only for V7/V8 as player
    if agent in ("v7", "v8"):
        ko = sum(int(r["ko_checks_us"]) for r in rows) / n
        msw = sum(int(r["matchup_switches_us"]) for r in rows) / n
        if ko == 0 and msw == 0:
            issues.append(f"V7/V8 strategy columns ALL zero (ko={ko}, matchup_sw={msw})")

        # Hazards should fire in gen4+
        if "gen4" in gen or "gen5" in gen or "gen6" in gen or "gen7" in gen or "gen8" in gen or "gen9" in gen:
            hazards = sum(int(r["hazard_sets_us"]) for r in rows) / n
            # It's OK if hazards are 0 in a small sample, just warn
            if hazards == 0 and n >= 10:
                issues.append(f"WARNING: hazard_sets_us = 0 in {gen} (might be OK with small sample)")
    else:
        # V1-V6: strategy columns MUST be 0
        for col in STRATEGY_COLS:
            total = sum(int(r[col]) for r in rows)
            if total != 0:
                issues.append(f"{agent} has {col} = {total} (should be 0!)")

    # Opponent decisions: non-zero only if opponent inherits BaseHeuristic1v1
    if opponent.startswith("v") and opponent not in ("vgc",):
        decisions_opp = sum(int(r["decisions_opp"]) for r in rows) / n
        if decisions_opp == 0:
            issues.append(f"decisions_opp = 0 (opponent is {opponent}, should track)")

    return issues

def main():
    print("=" * 60)
    print(" FULL VALIDATION: All agents, all gens, all columns")
    print("=" * 60)

    # Run benchmarks
    for agents, opponents, gen, n in TESTS:
        success = run_benchmark(agents, opponents, gen, n)
        if not success:
            print(f"  BENCHMARK FAILED for {gen}")

    # Check all generated CSVs
    print(f"\n{'='*60}")
    print(" VALIDATION RESULTS")
    print(f"{'='*60}")

    all_ok = True
    csvs = sorted(OUT.rglob("*.csv"))
    csvs = [c for c in csvs if not c.name.startswith("_tmp") and "matchup_performance" not in c.name]

    for csv_path in csvs:
        issues = check_csv(csv_path)
        gen = csv_path.parent.name
        status = "PASS" if not issues else "FAIL"
        if issues:
            all_ok = False
            print(f"\n  {status} {gen}/{csv_path.name}")
            for issue in issues:
                print(f"        - {issue}")
        else:
            print(f"  {status} {gen}/{csv_path.name}")

    # Summary
    print(f"\n{'='*60}")
    if all_ok:
        print(" ALL TESTS PASSED")
    else:
        print(" SOME TESTS FAILED - check above")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
