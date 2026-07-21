#!/usr/bin/env python
"""Deep audit of gen9 validation CSVs: all 70 columns, invariants, types."""

import csv
import math
from pathlib import Path

BASE = Path("/home/sirp/Documents/MUDS/TFM_Pokemon/data/testing/validation")
csvs = sorted([p for p in BASE.rglob("*.csv") if "matchup_performance" not in p.name])

EXPECTED_COLS = [
    # Cat A
    "battle_id", "format", "heuristic", "opponent", "winner", "won", "turns",
    # Cat B
    "decisions_us", "decisions_opp", "fallback_moves_us", "fallback_moves_opp",
    "error_moves_us", "error_moves_opp",
    # Cat C
    "voluntary_switches_us", "forced_switches_us", "voluntary_switches_opp", "forced_switches_opp",
    # Cat D
    "crit_us", "crit_opp", "miss_us", "miss_opp", "supereffective_us", "supereffective_opp",
    # Cat E
    "hazard_sets_us", "hazard_sets_opp", "hazard_removals_us", "hazard_removals_opp",
    "setup_uses_us", "setup_uses_opp", "ko_checks_us", "ko_checks_opp",
    "matchup_switches_us", "matchup_switches_opp", "terastallized_us", "terastallized_opp",
    # Cat F
    "ko_guards_us", "ko_guards_opp", "loop_guards_us", "loop_guards_opp",
    "xgb_switches_us", "xgb_switches_opp", "xgb_stays_us", "xgb_stays_opp",
    "xgb_prob_sum_us", "xgb_prob_sum_opp", "search_switches_us", "search_switches_opp",
    "search_moves_us", "search_moves_opp", "endgame_solves_us", "endgame_solves_opp",
    "search_diff_us", "search_diff_opp", "total_turns_us", "total_turns_opp",
    # Cat G
    "fainted_us", "fainted_opp", "remaining_pokemon_us", "remaining_pokemon_opp",
    "total_hp_us", "total_hp_opp", "hp_perc_us", "hp_perc_opp",
    "team_us", "team_opp", "side_conditions_us", "side_conditions_opp",
    "timestamp", "move_stats_us", "move_stats_opp",
]

INT_COLS = set([
    "won", "turns", "decisions_us", "decisions_opp", "fallback_moves_us", "fallback_moves_opp",
    "error_moves_us", "error_moves_opp", "voluntary_switches_us", "forced_switches_us",
    "voluntary_switches_opp", "forced_switches_opp", "crit_us", "crit_opp",
    "miss_us", "miss_opp", "supereffective_us", "supereffective_opp",
    "hazard_sets_us", "hazard_sets_opp", "hazard_removals_us", "hazard_removals_opp",
    "setup_uses_us", "setup_uses_opp", "ko_checks_us", "ko_checks_opp",
    "matchup_switches_us", "matchup_switches_opp", "terastallized_us", "terastallized_opp",
    "ko_guards_us", "ko_guards_opp", "loop_guards_us", "loop_guards_opp",
    "xgb_switches_us", "xgb_switches_opp", "xgb_stays_us", "xgb_stays_opp",
    "search_switches_us", "search_switches_opp", "search_moves_us", "search_moves_opp",
    "endgame_solves_us", "endgame_solves_opp", "search_diff_us", "search_diff_opp",
    "total_turns_us", "total_turns_opp", "fainted_us", "fainted_opp",
    "remaining_pokemon_us", "remaining_pokemon_opp",
])

FLOAT_COLS = set(["xgb_prob_sum_us", "xgb_prob_sum_opp", "total_hp_us", "total_hp_opp",
                  "hp_perc_us", "hp_perc_opp"])

STR_COLS = set(["battle_id", "format", "heuristic", "opponent", "winner",
                "team_us", "team_opp", "side_conditions_us", "side_conditions_opp",
                "timestamp", "move_stats_us", "move_stats_opp"])

col_status = {col: "PASS" for col in EXPECTED_COLS}
col_issues = {col: [] for col in EXPECTED_COLS}
invariant_issues = []
all_rows_count = 0

for csv_path in csvs:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)

    # Schema completeness
    missing = [c for c in EXPECTED_COLS if c not in cols]
    extra = [c for c in cols if c not in EXPECTED_COLS]
    if missing:
        invariant_issues.append(f"{csv_path.name}: MISSING COLS: {missing}")
    if extra:
        invariant_issues.append(f"{csv_path.name}: EXTRA COLS: {extra}")
    if len(cols) != 70:
        invariant_issues.append(f"{csv_path.name}: COL COUNT={len(cols)} != 70")

    all_rows_count += len(rows)
    for ri, row in enumerate(rows):
        ref = f"{csv_path.name}@row{ri}"

        # Per-column type/null check
        for col in EXPECTED_COLS:
            val = row.get(col, "")
            if val is None or val == "" or val in ("None", "nan", "NaN", "Inf", "inf", "-inf"):
                col_status[col] = "FAIL"
                col_issues[col].append(f"{ref}: null/empty: {repr(val)}")
                continue
            if col in INT_COLS:
                try:
                    int(val)
                except ValueError:
                    col_status[col] = "FAIL"
                    col_issues[col].append(f"{ref}: not int: {repr(val)}")
            elif col in FLOAT_COLS:
                try:
                    fv = float(val)
                    if math.isnan(fv) or math.isinf(fv):
                        col_status[col] = "FAIL"
                        col_issues[col].append(f"{ref}: NaN/Inf float: {repr(val)}")
                except ValueError:
                    col_status[col] = "FAIL"
                    col_issues[col].append(f"{ref}: not float: {repr(val)}")

        # Physical invariants
        try:
            won = int(row["won"]); winner = row["winner"]; heuristic = row["heuristic"]
            if (won == 1) != (winner == heuristic):
                invariant_issues.append(f"{ref}: won/winner mismatch: won={won} winner={winner} heuristic={heuristic}")
        except Exception: pass

        try:
            fu = int(row["fainted_us"]); ru = int(row["remaining_pokemon_us"])
            fo = int(row["fainted_opp"]); ro = int(row["remaining_pokemon_opp"])
            if fu + ru != 6:
                invariant_issues.append(f"{ref}: fainted_us({fu})+remaining_us({ru})={fu+ru}!=6")
            if fo + ro != 6:
                invariant_issues.append(f"{ref}: fainted_opp({fo})+remaining_opp({ro})={fo+ro}!=6")
        except Exception: pass

        try:
            hp = float(row["total_hp_us"]); hp_p = float(row["hp_perc_us"])
            if hp < 0 or hp > 6:
                invariant_issues.append(f"{ref}: total_hp_us={hp} out of [0,6]")
            if abs(hp / 6 - hp_p) > 0.001:
                invariant_issues.append(f"{ref}: hp_perc_us={hp_p:.4f} != total_hp_us/6={hp/6:.4f}")
        except Exception: pass

        try:
            hp = float(row["total_hp_opp"]); hp_p = float(row["hp_perc_opp"])
            if hp < 0 or hp > 6:
                invariant_issues.append(f"{ref}: total_hp_opp={hp} out of [0,6]")
            if abs(hp / 6 - hp_p) > 0.001:
                invariant_issues.append(f"{ref}: hp_perc_opp={hp_p:.4f} != total_hp_opp/6={hp/6:.4f}")
        except Exception: pass

        try:
            tera_u = int(row["terastallized_us"]); tera_o = int(row["terastallized_opp"])
            if tera_u not in (0, 1):
                invariant_issues.append(f"{ref}: terastallized_us={tera_u} not binary")
            if tera_o not in (0, 1):
                invariant_issues.append(f"{ref}: terastallized_opp={tera_o} not binary")
        except Exception: pass

        try:
            turns = int(row["turns"])
            if turns < 1:
                invariant_issues.append(f"{ref}: turns={turns} < 1")
        except Exception: pass

        try:
            fb = int(row["fallback_moves_us"]); em = int(row["error_moves_us"])
            # Just flag if non-zero for information (not a hard fail)
        except Exception: pass

# Print report
print("=" * 70)
print(f"DEEP AUDIT: gen9 validation CSVs ({len(csvs)} files, {all_rows_count} rows)")
print("=" * 70)
print()

pass_cols = [c for c in EXPECTED_COLS if col_status[c] == "PASS"]
fail_cols = [c for c in EXPECTED_COLS if col_status[c] != "PASS"]

print(f"COLUMN AUDIT: {len(pass_cols)}/70 PASS, {len(fail_cols)} FAIL")
print()

if fail_cols:
    print("FAILED COLUMNS:")
    for col in fail_cols:
        print(f"  ❌ {col}: {col_issues[col][:2]}")
else:
    print("✅ ALL 70 COLUMNS: type-safe, non-null, valid across all rows.")

print()
print(f"INVARIANT CHECKS: {len(invariant_issues)} issues")
if invariant_issues:
    for issue in invariant_issues:
        print(f"  ❌ {issue}")
else:
    print("✅ ALL PHYSICAL INVARIANTS SATISFIED:")
    print("   • won==1 iff winner==heuristic")
    print("   • fainted+remaining==6 (both sides)")
    print("   • total_hp in [0,6], hp_perc==total_hp/6")
    print("   • terastallized ∈ {0,1}")
    print("   • turns >= 1")

print()
print("=" * 70)
print("COMPLETE 70-COLUMN VALIDATION TABLE")
print("=" * 70)
print(f"{'#':<4} {'COLUMN':<35} {'TYPE':<8} {'STATUS'}")
print("-" * 70)
for i, col in enumerate(EXPECTED_COLS, 1):
    typ = "int" if col in INT_COLS else ("float" if col in FLOAT_COLS else "str")
    status = "✅ PASS" if col_status[col] == "PASS" else "❌ FAIL"
    print(f"{i:<4} {col:<35} {typ:<8} {status}")
