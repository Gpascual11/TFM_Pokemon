# Benchmark Development Log & Bugfix Summary

This document summarizes the development process, technical challenges, and robustness fixes implemented during the expansion of the PokéChamp rule-based benchmark.

## 1. Project Objective
Expand the existing singles benchmark to include a full matrix of rule-based agents against a comprehensive set of heuristic and baseline opponents.

**Final Configuration:**
- **Players (5):** `random`, `max_power`, `abyssal`, `one_step`, `safe_one_step`.
- **Opponents (12):** `v1`–`v6` (Heuristics), `random`, `max_power`, `simple_heuristic`, `abyssal`, `one_step`, `safe_one_step`.
- **Total Battles:** 6,000 (100 per matchup).

---

## 2. Errors Encountered & Solutions

### A. Naming Mismatch (`simple_heuristic` vs `abyssal`)
*   **Problem:** Previous benchmark data labeled the "Pokechamp standard heuristic" as `simple_heuristic`. However, PokéChamp's repo actually calls this agent `AbyssalPlayer`. This caused confusion with the official `simple_heuristic` from the `poke-env` library.
*   **Correction:** 
    1.  Renamed all existing `_vs_simple_heuristic.csv` files to `_vs_abyssal.csv`.
    2.  Updated `checkpoint_pokechamp.json` keys to use `_vs_abyssal`.
    3.  Used `sed` to patch internal CSV data where the opponent was still incorrectly labeled as `simple_heuristic`.

### B. Missing `SimpleHeuristicsPlayer` Import
*   **Problem:** PokéChamp's bundled fork of `poke_env` did not include the `SimpleHeuristicsPlayer` class, causing an `ImportError` when trying to run against the real baseline.
*   **Correction:** Created `true_simple_heuristic.py`, a local copy of the official `poke-env` baseline, to ensure we could benchmark against the correct reference point.

### C. Silent Deadlock in Heuristic V4 & V5
*   **Problem:** The benchmark would hang indefinitely with 0% CPU usage during `Matchup: safe_one_step vs v4`.
*   **Root Cause:** `HeuristicV4` and `HeuristicV5` attempted to calculate the "worst type multiplier" using `max()` on the opponent's types. If the opponent state was partially loaded (empty types), `max([])` threw a `ValueError`. Because this happened in the battle logic thread, it deadlocked the entire `poke-env` loop without crashing the process.
*   **Correction:** 
    1.  Added `len(types) > 0` safety guards to `v4.py` and `v5.py`.
    2.  **Robustness Wrapper:** Updated the base class `BaseHeuristic1v1` to wrap the `choose_move` logic in a try-except block. Now, if any version's logic crashes, the bot logs the error and falls back to a random move instead of hanging the benchmark.

### D. Server Memory Leaks & Hangs
*   **Problem:** Pokémon Showdown servers would hang after ~200 matches because the Node.js memory heap for battle workers never cleared.
*   **Correction:** Implemented an automatic "Safety Restart" in `benchmark.py`. The script now kills and restarts the Showdown server every 3 matchups, flushing the system memory and ensuring stability for long runs.

---

## 3. New Component: `safe_one_step`
We introduced the **`SafeOneStepPlayer`** agent. 
-   **Why:** The original PokéChamp `one_step` agent relied on local JSON files that were often missing or incomplete, causing it to block or loop infinitely.
-   **How:** `safe_one_step` implements the same 1-turn lookahead logic but uses purely `poke_env` data (type effectiveness, base power, STAB), making it 100% robust and dependency-free.

---

## 4. Final Verification
*   **Completion:** The benchmark now correctly resumes using `--resume` and skips finished matches.
*   **Visualization:** `generate_full_report.py` was updated to correctly group and label the 5x12 matrix.
*   **Final Ranking:**
    1.  **Abyssal** (~74% Win Rate)
    2.  **Safe One Step** (~57% Win Rate)
    3.  **One Step** (~54% Win Rate)
