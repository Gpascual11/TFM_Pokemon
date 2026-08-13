# Current-data re-run — results

This folder is a **snapshot** of the live-ladder and gen9 Elo passes. Canonical
family EDA figures live under `agents/heuristics_v1_v14/`, `agents/minimax_v15_v17/`,
`agents/mcts_v18_v20/`, and `agents/il_v21_v22/`.

Date of this snapshot: 2026-08-13.
Gauntlet: `data/benchmarks/all_10k/gen9randombattle` (10k games / matchup; **1k** if either
side is v18/v19/v20).
Ladder: `data/testing/logs/logs_v14_online/battle_history.csv`.

Taxonomy used everywhere below:

| IDs | Paradigm |
|---|---|
| v1–v14 | Heuristic ladder |
| v15–v17 | 1-ply minimax (analytic, no LocalSim) |
| v18–v20 | IS-MCTS (n = 1,000) |
| v21 | IL hybrid (XGB + v14) |
| v22 | IL pure (two XGBs, no v14) |

---

## 1. What was re-run, and why

| Notebook | Why it needed a current-data pass | This snapshot |
|---|---|---|
| `eda_online_bot.ipynb` | CSV had moved; markdown still talked about 100 games | `reruns/online_bot/` |
| gen9 tournament Elo (from `eda_tournament.ipynb` logic) | Old embedded plots; titles said “heuristic” for v15–v22 | `reruns/tournament_gen9/` |

Family EDAs (`eda_heuristics_v1_v14.ipynb`, `eda_minimax_v15_v17.ipynb`,
`eda_mcts_v18_v20.ipynb`, `eda_imitation_v21_v22.ipynb`) write to `agents/`, not here.
`dataset_integrity_verification.ipynb` already verified the 784-file matrix.

---

## 2. v14 vs humans (the notebook that was actually stale)

**431 live `gen9randombattle` games**, username `SirPThesis`.

| | Value |
|---|---|
| Raw win rate | **39.44% ± 4.6 pp** (170/431) |
| Turns ≥ 10 only | **35.43%** (n = 398) |
| Short games (turns < 10) | 33 — mostly opponent forfeits; they **inflate** the raw WR |
| Elo | 1085 → **1038** (range 1000–1263) |
| Errors | 0 (should be 0) |
| Fallbacks | 13 total |
| Window | 2026-06-09 21:54:55.175130 → 2026-06-10 18:32:07.274106 |

The June 2026 thesis-plan figure (98 games, 40.8%, Elo ~1151) is a **prefix** of this
log, not a different experiment. Elo **peaked at 1263** and the 98-game snapshot sat
near that local high. The full 431-game log **ends at 1038**. Cite **39.4% (n = 431,
CI ±4.6 pp)** and Elo 1085 → 1038. Do not keep quoting 40.8% / 1151 as if it were the
final sample.

On completed games (turns ≥ 10) v14 Terastallizes in 45/398 battles and wins **20%** of
those — Tera is firing from behind, not as v12’s every-game opener. KO checks stay
high (~16 / game), setup is almost unused (0.03 / game). That is the same v14 fingerprint
as in the bot-vs-bot gauntlet.

**How to use this number.** Bot-vs-bot said v14 is third among heuristics (62% gauntlet,
51% vs Abyssal) and v12 is first (69% / 60%). The ladder does **not** let you invert
that ranking. v14 was built to scout and profile humans; this sample only says that
design is not yet 50% vs the public ladder. It does not say v12 would do better online.

Figures: `online_bot/ladder_wr_elo.png`, `online_bot/ladder_win_vs_loss.png`.
Tables: `online_bot/ladder_headline.csv` and `*_by_outcome.csv`.

---

## 3. Heuristic ladder (v1–v14)

Gauntlet-weighted overall WR, 253,000 games each:

| agent   | regime          | added                                       |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   vol_switches |   matchup_switches |   tera / game |   setup / game |   hazards / game |   ko_checks / game |   fallbacks / game |
|:--------|:----------------|:--------------------------------------------|--------:|-------------:|----------:|------------:|------------:|---------------:|-------------------:|--------------:|---------------:|-----------------:|-------------------:|-------------------:|
| v1      | Plateau         | greedy bp×type×STAB; no switches            |  253000 |      44.2462 |  0.193539 |     17.9959 |    0.875818 |        1.00726 |           0        |    0          |       0        |        0         |          0         |          4.65327   |
| v2      | Plateau         | stats, burn, tracking                       |  253000 |      44.704  |  0.193737 |     17.9783 |    0.88634  |        1.02515 |           0        |    0          |       0        |        0         |          0         |          4.58929   |
| v3      | Plateau         | more damage fidelity                        |  253000 |      44.7494 |  0.193756 |     17.9778 |    0.888953 |        1.02546 |           0        |    0          |       0        |        0         |          0         |          4.54742   |
| v4      | Plateau         | field / weather                             |  253000 |      45.504  |  0.194044 |     17.9637 |    0.905162 |        1.02562 |           0        |    0          |       0        |        0         |          0         |          4.57273   |
| v5      | Plateau         | boost stages                                |  253000 |      45.8636 |  0.194165 |     17.9562 |    0.916091 |        1.02474 |           0        |    0          |       0        |        0         |          0         |          4.54654   |
| v6      | Plateau         | Toxic / outspeed pivot                      |  253000 |      45.2814 |  0.193963 |     17.9855 |    0.899036 |        1.02533 |           0        |    0          |       0        |        0         |          0         |          4.59123   |
| v7      | Positional      | hazards, setup, KO, matchup switch          |  253000 |      54.2462 |  0.194129 |     17.991  |    1.17192  |        1.46796 |           0.410652 |    0          |       0        |        0         |          0         |          2.17503   |
| v8      | Positional      | items, abilities, screens, TR               |  253000 |      55.4285 |  0.193681 |     17.9304 |    1.19809  |        1.48377 |           0.41219  |    0.00159684 |       0        |        0         |          0.0643715 |          2.18072   |
| v9      | Tempo-safe      | hazards/setup only on free turns            |  253000 |      58.8613 |  0.191749 |     17.9043 |    1.43923  |        1.46294 |           0.396123 |    0.00139921 |       1.64083  |        0.166577  |          0         |          2.16236   |
| v10     | Positional      | status, sack ≤20% HP, U-turn                |  253000 |      55.6565 |  0.193582 |     17.9071 |    1.19457  |        1.42646 |           0.387083 |    0.00162055 |       0        |        0         |          0.0643794 |          2.16463   |
| v11     | Tempo-safe      | v9 tempo + v10 status/pivot                 |  253000 |      59.2625 |  0.191461 |     17.8757 |    1.44064  |        1.40162 |           0.359652 |    0.00145059 |       1.64606  |        0.166735  |          0.0687352 |          2.1257    |
| v12     | Tera / preview  | Tera + preview lead + fainted switch-in     |  253000 |      69.0146 |  0.180195 |     17.8646 |    1.84197  |        1.36942 |           0.246964 |    0.95519    |       1.74626  |        0.175024  |          0.072087  |          0.0143202 |
| v13     | Set prediction  | set prediction, conservative Tera, recovery |  253000 |      67.6261 |  0.182326 |     19.0941 |    2.01482  |        3.57879 |           2.56958  |    0.196265   |       1.58311  |        0.310249  |          0.0712569 |          0.0119368 |
| v14     | Yomi / scouting | Yomi, T1–3 scouting, 16-step, 1-ply endgame |  253000 |      62.03   |  0.18911  |     18.5269 |    1.48531  |        2.09033 |           1.04366  |    0.335166   |       0.206625 |        0.0335652 |         14.6287    |          0.0192688 |

Three jumps, then an inversion:

- Plateau v1–v6 ≈ 44–46%. Extra damage math does not win Random Battles.
- v7 ≈ 54% (+9 pp): hazards, KO, matchup switching.
- v9 / v11 ≈ 59%: setup only on free turns.
- **v12 = 69.0%**: Tera + preview + fainted switch-in. First internal agent to beat Abyssal (59.9%).
- **v12 ≥ v13 > v14** (69.0 / 67.6 / 62.0). Genealogy said the opposite. H2H at 10k:
  v12 vs v13 is a coin flip (50.7 / 48.9); v14 loses to both.

`setup_uses_us` / `hazard_sets_us` are 0 for v7/v8/v10 — schema gap, not “they never set rocks”.

---

## 4. 1-ply minimax (v15–v17)

| agent                            |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   search_fire_%_turns |   search_moves / game |   search_switches / game |   search_diff / game |   override_%_of_search |   ko_checks / game |   endgame / game |   loop_guards / game |   setup / game |   hazards / game |   tera / game |
|:---------------------------------|--------:|-------------:|----------:|------------:|------------:|----------------------:|----------------------:|-------------------------:|---------------------:|-----------------------:|-------------------:|-----------------:|---------------------:|---------------:|-----------------:|--------------:|
| v15 maximin (HP leaf)            |  253000 |      53.7992 |  0.19427  |     18.8113 |     1.28317 |               17.6447 |               3.47385 |                 0.978087 |              2.80423 |                66.54   |            14.3307 |        0.0253043 |             0.276763 |       0.207024 |        0.0493953 |      0.39596  |
| v16 maximin (positional bonuses) |  253000 |      54.3004 |  0.194111 |     19.025  |     1.29128 |               17.5851 |               3.61528 |                 0.945095 |              2.94362 |                67.2809 |            14.3325 |        0.0261186 |             0.259261 |       0.213075 |        0.0442569 |      0.390372 |
| v17 hybrid (v14 prior +0.15)     |  253000 |      57.8885 |  0.192393 |     18.7957 |     1.38682 |               16.2934 |               3.13733 |                 1.05194  |              1.65103 |                36.6233 |            14.4882 |        0.0261818 |             0.335549 |       0.208775 |        0.0427589 |      0.380336 |

Search fires on ~16–18% of turns (KO short-circuit is the rest). Unconstrained maximin
(v15/v16) overrides v14 on **~67%** of those turns; v16’s setup/hazard leaf bonuses do
not raise setup uses (~0.21, v14-like). The +0.15 v14 prior (**v17**) is the only 1-ply
upgrade that moves WR. v17 still loses to v14 (43.6%) and to v12 (40.9%) at n = 10k.

---

## 5. IS-MCTS (v18–v20)

All cells n = 1,000. Do not mix this 28k overall WR with the 253k heuristic/minimax/IL overall.

| agent                      |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   search_fire_%_turns |   search_moves / game |   search_switches / game |   search_diff / game |   override_%_of_search |   ko_checks / game |   endgame / game |   loop_guards / game |   setup / game |   hazards / game |   tera / game |
|:---------------------------|--------:|-------------:|----------:|------------:|------------:|----------------------:|----------------------:|-------------------------:|---------------------:|-----------------------:|-------------------:|-----------------:|---------------------:|---------------:|-----------------:|--------------:|
| v18 UCB1 (HP leaf)         |   28000 |      54.0214 |  0.583725 |     18.5307 |     1.2075  |               18.0559 |               3.7565  |                 0.608107 |             3.12561  |                71.3359 |            14.1627 |        0.0333571 |             0.09825  |       0.223393 |        0.04625   |      0.405536 |
| v19 UCB1 (positional leaf) |   28000 |      53.2857 |  0.584356 |     18.5756 |     1.21621 |               17.6207 |               3.39714 |                 0.873179 |             3.07329  |                71.0974 |            14.1925 |        0.0291429 |             0.259607 |       0.21875  |        0.0468929 |      0.3935   |
| v20 PUCT (v14 prior 0.70)  |   28000 |      59.6607 |  0.574588 |     18.3269 |     1.39729 |               15.5043 |               2.60439 |                 1.06875  |             0.786714 |                18.6586 |            14.5435 |        0.0280357 |             0.346571 |       0.2015   |        0.0352857 |      0.388071 |

Same KO backup (~16–18% search). UCB1 (v18/v19) overrides v14 on **~71%** of tree
decisions; losers override more (horizon effect). A richer leaf (v19) does nothing.
PUCT with a v14 prior (**v20**) is the only 5-ply upgrade — by disagreeing less (~19%
override), not by seeing further. Setup/hazards stay v14-like. v20 vs v12 is 42.7%;
vs v14 is 47.0%.

---

## 6. Imitation learning (v21–v22)

| agent                  |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   vol_switches |   xgb_fire_%_turns |   xgb_switch_share_% |   mean_p_switch |   ko_guards / game |   endgame / game |   loop_guards / game |   fallback / game |   error / game |
|:-----------------------|--------:|-------------:|----------:|------------:|------------:|---------------:|-------------------:|---------------------:|----------------:|-------------------:|-----------------:|---------------------:|------------------:|---------------:|
| v21 Hybrid (XGB + v14) |  253000 |      58.7075 |  0.191856 |     18.2042 |    1.33134  |        1.97813 |            15.2183 |              35.5475 |       0.0798704 |            13.8473 |         0.031751 |             0.381534 |         0         |              0 |
| v22 Pure IL (two XGBs) |  253000 |      33.4925 |  0.183909 |     20.0688 |    0.703403 |        3.72474 |            79.9134 |              15.1899 |       0.351111  |             0      |         0        |             1.9196   |         0.0112727 |              0 |

Same XGBoost macro, same τ = 0.5525. v21 keeps v14’s KO/endgame and only asks XGB on
**15%** of turns (WR 58.7%, ≈ v9/v11). v22 is the clone with no v14: XGB on 80% of
turns, zero KO guards, loop guards in 97% of games, WR **33.5%** (below v1). v21 beats
v22 28/28 matchups. Hybrid IL is a competent mid-heuristic; pure cloning is not.

---

## 7. Cross-paradigm ranking (gen9, as us)

Bradley-Terry Elo (anchor `random` = 1000), using both seats of every directed file.
MCTS agents have 56k games in this model (28k as us + 28k as opp); everyone else 506k.
v12 and v13 are clearly first. **v14 is tied with Abyssal and Simple Heuristic** (~1755
Elo) — the same coin-flip vs those two baselines already seen in the 10k cells.
v20 / v21 / v17 follow, still below the knowledge ceiling.

| Rank | Agent | Paradigm | Elo |
|---:|---|---|---:|
| 1 | v12 | Heuristic | 1812 |
| 2 | v13 | Heuristic | 1802 |
| 3 | simple_heuristic | Baseline | 1755 |
| 4 | v14 | Heuristic | 1755 |
| 5 | abyssal | Baseline | 1755 |
| 6 | v20 | MCTS (n=1k cells) | 1742 |
| 7 | v11 | Heuristic | 1733 |
| 8 | v9 | Heuristic | 1730 |
| 9 | v21 | IL hybrid | 1729 |
| 10 | v17 | Minimax | 1722 |
| … | v22 | IL pure | 1529 |
| … | random | Baseline | 1000 |

Overall WR as *us* (MCTS rows are 28k equally weighted opponents; others 253k with
MCTS underweighted — compare matchup cells, not these two overalls, when ranking v20
against v11):

| heuristic        |   games |   wins |   win_rate_% | paradigm   |
|:-----------------|--------:|-------:|-------------:|:-----------|
| v12              |  253000 | 174607 |      69.0146 | Heuristic  |
| v13              |  253000 | 171094 |      67.6261 | Heuristic  |
| v14              |  253000 | 156936 |      62.03   | Heuristic  |
| abyssal          |  253000 | 156855 |      61.998  | Baseline   |
| simple_heuristic |  253000 | 156674 |      61.9265 | Baseline   |
| v20              |   28000 |  16705 |      59.6607 | MCTS       |
| v11              |  253000 | 149934 |      59.2625 | Heuristic  |
| v9               |  253000 | 148919 |      58.8613 | Heuristic  |
| v21              |  253000 | 148530 |      58.7075 | IL Hybrid  |
| v17              |  253000 | 146458 |      57.8885 | Minimax    |
| v10              |  253000 | 140811 |      55.6565 | Heuristic  |
| v8               |  253000 | 140234 |      55.4285 | Heuristic  |
| v16              |  253000 | 137380 |      54.3004 | Minimax    |
| v7               |  253000 | 137243 |      54.2462 | Heuristic  |
| v18              |   28000 |  15126 |      54.0214 | MCTS       |
| v15              |  253000 | 136112 |      53.7992 | Minimax    |

The hierarchical moral is the same three times: the residual that **trusts v14**
(v17, v20, v21) is the only variant that moves; the residual that **replaces v14**
(v15/v16, v18/v19, v22) overrides more and wins less. None of them beat v12.

---

## 8. Folder map

```
reruns/
  RESULTS.md                          ← this file
  online_bot/                         ← live ladder
  tournament_gen9/                    ← Elo + overall WR
```

Family figures: `src/p00_core/reporting/agents/{heuristics_v1_v14,minimax_v15_v17,mcts_v18_v20,il_v21_v22}/`.

Deep thesis write-up (argument, not just tables):
`src/p00_core/reporting/heuristics_and_imitation_thesis_analysis.md`.
