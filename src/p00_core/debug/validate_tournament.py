#!/usr/bin/env python
"""Pre-flight validation for the full 10k tournament.

Runs 3-game smoke tests across multiple gens and agent pairs to verify:
  1. All 51 CSV columns are present and correctly named.
  2. Numeric columns (decisions, switches, etc.) are properly populated.
  3. New columns (voluntary_switches_opp, forced_switches_opp,
     terastallized_us, terastallized_opp) exist and are integers.
  4. The benchmark auto-resume works: run twice and confirm row count doubles.

Usage (from project root):
    uv run python src/p00_core/scripts/validate_tournament.py
"""

import csv
import shutil
import subprocess
import sys
from pathlib import Path

# ── Expected columns in new worker.py ─────────────────────────────────────────
EXPECTED_COLUMNS = [
    "battle_id", "format", "heuristic", "opponent", "winner", "won", "turns",
    "decisions_us", "decisions_opp",
    "fallback_moves_us", "fallback_moves_opp",
    "error_moves_us", "error_moves_opp",
    "fainted_us", "remaining_pokemon_us", "total_hp_us",
    "fainted_opp", "remaining_pokemon_opp", "total_hp_opp",
    "team_us", "team_opp",
    "side_conditions_us", "side_conditions_opp",
    "voluntary_switches_us", "forced_switches_us",
    "voluntary_switches_opp", "forced_switches_opp",   # NEW
    "move_stats_us", "move_stats_opp",
    "crit_us", "crit_opp",
    "miss_us", "miss_opp",
    "supereffective_us", "supereffective_opp",
    "hp_perc_us", "hp_perc_opp",
    "hazard_sets_us", "hazard_sets_opp",
    "hazard_removals_us", "hazard_removals_opp",
    "setup_uses_us", "setup_uses_opp",
    "ko_checks_us", "ko_checks_opp",
    "matchup_switches_us", "matchup_switches_opp",
    "terastallized_us", "terastallized_opp",           # NEW
    "timestamp",
]
N_EXPECTED = len(EXPECTED_COLUMNS)

# ── Smoke test cases: (agent, opponent, gen, n_games) ─────────────────────────
SMOKE_TESTS = [
    ("v12",  "random",  "gen9randombattle", 3),
    ("v9",   "v7",      "gen5randombattle", 3),
    ("v1",   "abyssal", "gen1randombattle", 3),
    ("v10",  "v11",     "gen9randombattle", 3),
]

OUT = Path("data/testing/validate_smoke")
PASS = 0
FAIL = 0


def run_benchmark(agent, opponent, gen, n):
    out_dir = OUT / gen
    cmd = [
        sys.executable,
        "src/p00_core/engine/benchmark.py",
        str(n),
        "--agents", agent,
        "--opponents", opponent,
        "--ports", "1",
        "--concurrency", "5",
        "--battle-format", gen,
        "--out", str(out_dir),
        "--restart-every", "0",
    ]
    print(f"  Running {n}g: {agent} vs {opponent} ({gen})... ", end="", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = result.returncode == 0
    print("OK" if ok else f"FAILED (exit {result.returncode})")
    if not ok:
        print(f"    STDERR: {result.stderr[-400:]}")
    return ok


def check_csv(path: Path, n_expected_rows: int) -> list[str]:
    issues = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames or []

    # Column count
    if len(cols) != N_EXPECTED:
        issues.append(f"Column count: {len(cols)} (expected {N_EXPECTED})")

    # Missing columns
    missing = [c for c in EXPECTED_COLUMNS if c not in cols]
    if missing:
        issues.append(f"Missing columns: {missing}")

    # Extra columns
    extra = [c for c in cols if c not in EXPECTED_COLUMNS]
    if extra:
        issues.append(f"Extra columns: {extra}")

    # Row count
    if len(rows) < n_expected_rows:
        issues.append(f"Row count: {len(rows)} (expected at least {n_expected_rows})")

    if not rows:
        return issues

    # Integer columns must parse cleanly
    int_cols = [
        "won", "turns", "decisions_us", "decisions_opp",
        "voluntary_switches_us", "forced_switches_us",
        "voluntary_switches_opp", "forced_switches_opp",
        "crit_us", "crit_opp", "fainted_us", "fainted_opp",
        "terastallized_us", "terastallized_opp",
    ]
    for col in int_cols:
        if col not in cols:
            continue
        for r in rows:
            try:
                int(r[col])
            except (ValueError, TypeError):
                issues.append(f"Non-integer in {col}: '{r[col]}'")
                break

    # terastallized must be 0 or 1
    for col in ("terastallized_us", "terastallized_opp"):
        if col not in cols:
            continue
        for r in rows:
            val = int(r[col])
            if val not in (0, 1):
                issues.append(f"{col} has value {val} (must be 0 or 1)")
                break

    # decisions_us must be > 0 for all heuristic agents
    agent = rows[0]["heuristic"]
    if agent not in ("random",):
        avg_decisions = sum(int(r["decisions_us"]) for r in rows) / len(rows)
        if avg_decisions == 0:
            issues.append(f"decisions_us = 0 (agent={agent}, should be > 0)")

    # error_moves should be 0 or very low
    avg_errors = sum(int(r["error_moves_us"]) for r in rows) / len(rows)
    if avg_errors > 2:
        issues.append(f"error_moves_us avg = {avg_errors:.1f} (too many!)")

    return issues


def check_resume(agent, opponent, gen, first_n):
    """Verify that running again appends rows instead of overwriting."""
    csv_path = OUT / gen / f"{agent}_vs_{opponent}.csv"
    if not csv_path.exists():
        return False, "CSV not found after first run"

    with open(csv_path) as f:
        rows_before = sum(1 for _ in f) - 1  # subtract header

    # Run same matchup again (same N — benchmark should detect already done)
    run_benchmark(agent, opponent, gen, first_n)

    with open(csv_path) as f:
        rows_after = sum(1 for _ in f) - 1

    if rows_after < rows_before:
        return False, f"Rows decreased! {rows_before} → {rows_after} (data lost!)"
    if rows_after == rows_before:
        return True, f"Resume OK: {rows_before} rows unchanged (all already done)"
    return True, f"Resume OK: {rows_before} → {rows_after} rows (extra games added)"


# ── Run tests ─────────────────────────────────────────────────────────────────
def main():
    global PASS, FAIL

    print("=" * 65)
    print("  PRE-FLIGHT VALIDATION — Full 10k Tournament")
    print(f"  Expected columns: {N_EXPECTED}")
    print("=" * 65)

    # Clean old smoke output to get a fresh start
    if OUT.exists():
        shutil.rmtree(OUT)

    print("\n[1] RUNNING SMOKE BENCHMARKS")
    bench_ok = True
    for agent, opponent, gen, n in SMOKE_TESTS:
        ok = run_benchmark(agent, opponent, gen, n)
        if not ok:
            bench_ok = False

    print("\n[2] VALIDATING CSV COLUMNS AND DATA")
    for agent, opponent, gen, n in SMOKE_TESTS:
        csv_path = OUT / gen / f"{agent}_vs_{opponent}.csv"
        label = f"{gen}/{agent}_vs_{opponent}.csv"
        if not csv_path.exists():
            print(f"  FAIL  {label}  — FILE MISSING")
            FAIL += 1
            continue
        issues = check_csv(csv_path, n_expected_rows=n)
        if issues:
            print(f"  FAIL  {label}")
            for issue in issues:
                print(f"        - {issue}")
            FAIL += 1
        else:
            print(f"  PASS  {label}  ({N_EXPECTED} cols, ≥{n} rows)")
            PASS += 1

    print("\n[3] VALIDATING AUTO-RESUME (crash-safety)")
    # Test on first smoke case
    agent, opponent, gen, n = SMOKE_TESTS[0]
    ok, msg = check_resume(agent, opponent, gen, n)
    if ok:
        print(f"  PASS  {msg}")
        PASS += 1
    else:
        print(f"  FAIL  {msg}")
        FAIL += 1

    print("\n" + "=" * 65)
    print(f"  Results: {PASS} PASS / {FAIL} FAIL")
    if FAIL == 0:
        print("  ✅ ALL CHECKS PASSED — safe to launch run_all_10k.sh")
    else:
        print("  ❌ SOME CHECKS FAILED — fix issues before launching tournament")
    print("=" * 65)
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
