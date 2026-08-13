# Dataset Integrity Verification Notebook — Review

## Overview
Reviewed [dataset_integrity_verification.ipynb](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p00_core/reporting/dataset_integrity_verification.ipynb) covering 784 CSV files (28 agents × 28 opponents) in `data/benchmarks/all_10k/gen9randombattle`.

---

## ✅ Cells That Pass Correctly

| Cell | Check | Result | Verdict |
|------|-------|--------|---------|
| 1 | Setup & Config | 28 agents, 784 matchups, REDUCED_AGENTS={v18,v19,v20} | ✅ Correct |
| 2 | File Inventory | 784/784 found, 0 missing, 0 unexpected, 5.80 GB total | ✅ Correct |
| 3 | Row Counts | 625 × 10k + 159 × 1k = 6,409,000 total | ✅ Correct (25²=625, 784−625=159) |
| 4 | Schema Check | 347 base (50-col) + 437 extended (70-col), 0 errors | ✅ Correct |
| 5 | Filename ↔ Content | heuristic/opponent match filenames, 0 errors | ✅ Correct |
| 6 | Domain Checks | won∈{0,1}, format consistency, winner consistency | ✅ Correct |
| 7 | Numeric Ranges | All sampled columns within bounds (70 files) | ✅ Correct |
| 8 | Null Analysis | Only expected nulls (side_conditions ~91%, move_stats ~0.003%) | ✅ Correct |
| 9 | Timestamps | 0 missing, 0 malformed, valid ISO-8601, range 2026-05-27→2026-08-12 | ✅ Correct |
| 10 | Duplicates | 3M battle_id clones (expected: worker ports), 0 true content dupes | ✅ Correct |
| 11 | Battle ID Format | All match legacy or worker-prefixed pattern | ✅ Correct |
| 12 | Team Strings | 0 errors, US side 99.99% has 6 mons, OPP side 70.26% fully revealed | ✅ Correct |

---

## ⚠️ Findings Requiring Attention

### 1. Cell 13 — US Fainted+Remaining Invariant (429 violations)
**Status**: This is a **real data quality finding**, not a notebook bug.

429 rows across 249 files have `fainted_us + remaining_pokemon_us = 5` instead of 6. Spot-checked examples:
- `abyssal_vs_abyssal.csv`: row 4348 (lost, sum=5), row 8953 (won, sum=5)
- `abyssal_vs_v6.csv`: 4 violations, all with sum=5

These appear to be edge cases where a Pokémon wasn't tracked (possibly Zoroark illusion, or self-destruct interaction). Rate: 429/6,409,000 = **0.0067%** — negligible but worth noting.

> [!NOTE]
> The notebook correctly identifies these violations. The interpretation in the markdown header (Cell 13) initially says `fainted + remaining ≤ 6`, but the code correctly checks for `!= 6` on the US side and `> 6` on the OPP side, which is the right approach.

### 2. Cell 14 — Win/Fainted Mismatches (1,231 total)
**Status**: Correctly identified and properly explained.

- 738 "won but opp not all fainted" — expected (unrevealed mons in random battles)
- 493 "lost but us not all fainted" — edge cases (timer/forfeit/disconnect + the 429 tracking gaps from Cell 13)

Rate: 0.0192% — acceptable.

### 3. Cell 15 — Reciprocal Win-Rate Errors (3 pairs)
**Status**: Correctly identified, statistically valid concern.

| Pair | Sum | Tolerance | Issue |
|------|-----|-----------|-------|
| v16_vs_v9 + v9_vs_v16 | 1.0209 | 0.0182 | Both 10k, deviation exceeds 99% CI |
| v17_vs_v20 + v20_vs_v17 | 1.0620 | 0.0577 | Both 1k, deviation exceeds 99% CI |
| v22_vs_v8 + v8_vs_v22 | 0.9769 | 0.0182 | Both 10k, deviation exceeds 99% CI |

> [!IMPORTANT]
> These 3 reciprocal violations suggest that some matchups weren't fully symmetric (possibly different RNG seeds, server conditions, or Showdown versions between runs). Worth investigating whether these matchups were run at different times or with different configurations.

---

## ❌ Bug: Cell 17 — Summary Report Fails

**Error**: `NameError: name 'over6_violations' is not defined`

Cell 17 references `over6_violations` on **line 15** of its source, but this variable was renamed to `opp_over6_violations` when Cell 13 was rewritten to separate US and OPP invariant checks.

### Fix
In Cell 17, change:
```diff
-    ("Fainted+Remaining Invariant (≤6 both sides)", over6_violations == 0),
+    ("Fainted+Remaining Invariant (≤6 both sides)", opp_over6_violations == 0),
```

> [!WARNING]
> This bug prevents the final summary report from executing. After fixing, re-run Cell 17 to get the complete integrity dashboard.

---

## 📊 Dataset Health Summary

| Metric | Value |
|--------|-------|
| Total Files | 784 / 784 |
| Total Rows | 6,409,000 |
| 10k-game files | 625 |
| 1k-game files | 159 (v18/v19/v20 matchups) |
| Disk Size | 5.80 GB |
| Content Duplicates | 0 |
| Critical Nulls | 0 |
| Schema Errors | 0 |

**Overall**: Dataset is clean and ready for analysis. The only notebook issue is the Cell 17 `NameError` bug that needs fixing.
