#!/usr/bin/env python
"""Post-hoc patch: fix remaining_pokemon_opp and hp_perc_opp in existing CSVs.

No re-run needed:
- remaining_pokemon_opp = 6 - fainted_opp   (fainted_opp is always correct)
- hp_perc_opp = round(total_hp_opp / 6, 3)  (total_hp_opp is always correct)
"""
import csv
from pathlib import Path

TEAM_SIZE = 6

ROOT = Path("/home/sirp/Documents/MUDS/TFM_Pokemon")
BASE_DIRS = [
    ROOT / "data/testing/validation",
    ROOT / "data/benchmarks/verification_100games_gen9",
    ROOT / "data/benchmarks/quick_test_minimax",
]

FIXED_COLS = {"remaining_pokemon_opp", "hp_perc_opp"}

patched_files = 0
patched_rows = 0

for base in BASE_DIRS:
    for csv_path in sorted(base.rglob("*.csv")):
        if "matchup_performance" in csv_path.name:
            continue
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        if not all(c in fieldnames for c in ("fainted_opp", "total_hp_opp", "remaining_pokemon_opp", "hp_perc_opp")):
            print(f"SKIP (missing cols): {csv_path.name}")
            continue

        changed = 0
        for row in rows:
            try:
                fainted_opp = int(row["fainted_opp"])
                total_hp_opp = float(row["total_hp_opp"])

                new_remaining = TEAM_SIZE - fainted_opp
                new_hp_perc = round(total_hp_opp / TEAM_SIZE, 3)

                if int(row["remaining_pokemon_opp"]) != new_remaining:
                    row["remaining_pokemon_opp"] = str(new_remaining)
                    changed += 1
                if abs(float(row["hp_perc_opp"]) - new_hp_perc) > 0.0005:
                    row["hp_perc_opp"] = str(new_hp_perc)
                    changed += 1
            except (ValueError, KeyError) as e:
                print(f"  ERROR in {csv_path.name}: {e}")
                continue

        if changed:
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"PATCHED {csv_path.relative_to(base.parent.parent)}: {changed} cell(s) corrected")
            patched_files += 1
            patched_rows += changed
        else:
            print(f"OK (no changes): {csv_path.relative_to(base.parent.parent)}")

print(f"\nDone. {patched_files} file(s) patched, {patched_rows} cell(s) corrected.")
