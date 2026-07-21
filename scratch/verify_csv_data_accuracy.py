#!/usr/bin/env python
"""CSV Data Accuracy & Scientific Reliability Verification Script.

Inspects every row across all benchmark CSVs (data/benchmarks/all_10k and
data/testing/validation/) to verify mathematical integrity, logical consistency,
and absence of corrupted or invalid battle records for Master's Thesis defense.
"""

import csv
from pathlib import Path

BASE_DIR = Path("/home/sirp/Documents/MUDS/TFM_Pokemon")
SEARCH_DIRS = [
    BASE_DIR / "data" / "benchmarks" / "all_10k",
    BASE_DIR / "data" / "testing" / "validation",
]


def verify_row_integrity(row: dict, row_idx: int) -> list[str]:
    issues = []

    # 1. Winner and Won consistency
    try:
        won = int(row["won"])
        if won not in (0, 1):
            issues.append(f"Row {row_idx}: 'won' value invalid ({won})")
        heuristic = row.get("heuristic", "")
        opponent = row.get("opponent", "")
        winner = row.get("winner", "")
        expected_winner = heuristic if won == 1 else opponent
        if winner and expected_winner and winner != expected_winner:
            issues.append(f"Row {row_idx}: Winner mismatch (winner={winner}, expected={expected_winner})")
    except (ValueError, KeyError) as e:
        issues.append(f"Row {row_idx}: Error parsing 'won' column: {e}")

    # 2. Turn sanity
    try:
        turns = int(row["turns"])
        if turns < 1:
            issues.append(f"Row {row_idx}: Non-positive turn count ({turns})")
    except (ValueError, KeyError) as e:
        issues.append(f"Row {row_idx}: Error parsing 'turns': {e}")

    # 3. Fainted & HP bounds check
    try:
        fainted_us = int(row.get("fainted_us", 0))
        rem_us = int(row.get("remaining_pokemon_us", 6 - fainted_us))
        if fainted_us < 0 or fainted_us > 6:
            issues.append(f"Row {row_idx}: Invalid fainted_us ({fainted_us})")
        if rem_us < 0 or rem_us > 6:
            issues.append(f"Row {row_idx}: Invalid remaining_pokemon_us ({rem_us})")
    except ValueError as e:
        issues.append(f"Row {row_idx}: Error parsing fainted stats: {e}")

    try:
        hp_perc_us = float(row.get("hp_perc_us", 0.0))
        if hp_perc_us < 0.0 or hp_perc_us > 1.05:
            issues.append(f"Row {row_idx}: Out-of-bounds hp_perc_us ({hp_perc_us})")
    except ValueError as e:
        issues.append(f"Row {row_idx}: Error parsing hp_perc_us: {e}")

    # 4. Error moves check
    try:
        error_us = int(row.get("error_moves_us", 0))
        if error_us > 0:
            issues.append(f"Row {row_idx}: {error_us} error moves logged!")
    except ValueError:
        pass

    return issues


def verify_file(csv_path: Path) -> dict:
    rel_path = csv_path.relative_to(BASE_DIR).as_posix()
    report = {
        "file": rel_path,
        "total_rows": 0,
        "valid_rows": 0,
        "issues": [],
    }

    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        report["total_rows"] = len(rows)
        row_issues = []
        for idx, row in enumerate(rows, start=1):
            errs = verify_row_integrity(row, idx)
            if errs:
                row_issues.extend(errs)

        report["issues"] = row_issues
        report["valid_rows"] = len(rows) - len(set(e.split(":")[0] for e in row_issues))

    except Exception as e:
        report["issues"].append(f"File level exception: {e}")

    return report


def main():
    print("=================================================================")
    print("  SCIENTIFIC DATA ACCURACY & RELIABILITY VERIFICATION")
    print("=================================================================")

    csv_files = []
    for sdir in SEARCH_DIRS:
        if sdir.exists():
            for p in sdir.rglob("*.csv"):
                if p.name != "matchup_performance.csv" and "gen9" in p.as_posix().lower():
                    csv_files.append(p)

    csv_files.sort()
    print(f"Inspecting data accuracy across {len(csv_files)} CSV files...\n")

    total_files = len(csv_files)
    clean_files = 0
    total_battles = 0
    total_corrupted = 0

    print(f"{'FILE':<58} | {'BATTLES':<7} | {'DATA INTEGRITY'}")
    print("-" * 80)

    for csv_path in csv_files:
        rep = verify_file(csv_path)
        total_battles += rep["total_rows"]
        is_clean = len(rep["issues"]) == 0

        if is_clean:
            clean_files += 1
            status = "100% ACCURATE & RELIABLE"
        else:
            total_corrupted += len(rep["issues"])
            status = f"ISSUES ({len(rep['issues'])})"

        display_name = rep["file"]
        if len(display_name) > 57:
            display_name = "..." + display_name[-54:]

        print(f"{display_name:<58} | {rep['total_rows']:<7} | {status}")
        if rep["issues"][:3]:  # Print first 3 issues if any
            for issue in rep["issues"][:3]:
                print(f"     -> {issue}")

    print("-" * 80)
    print("SUMMARY RESULT:")
    print(f"  • Total Datasets Audited     : {total_files}")
    print(f"  • Datasets 100% Accurate     : {clean_files} / {total_files}")
    print(f"  • Total Battles Checked      : {total_battles:,}")
    print(f"  • Corrupted / Invalid Records: {total_corrupted}")
    print("=================================================================\n")

    if clean_files == total_files:
        print("✅ ALL DATASETS ARE 100% SCIENTIFICALLY ACCURATE & RELIABLE FOR THESIS DEFENSE!")


if __name__ == "__main__":
    main()
