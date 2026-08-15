# 1-Ply Minimax EDA — v15 / v16 / v17

Deep thesis write-up: [`../../heuristics_and_imitation_thesis_analysis.md`](../../heuristics_and_imitation_thesis_analysis.md).

Source: `data/benchmarks/all_10k/gen9randombattle` (each agent as us vs 28 opponents;
10k games, or 1k vs v18/v19/v20).
Search: analytic 1-ply maximin, approximate damage range, opponent damage × 1.5.

## Architecture in one paragraph

All three agents are 1-ply maximin on top of HeuristicV14. For each legal
action they evaluate the worst-case reply among **revealed** opponent moves
and a hypothetical switch.
**v15** uses an HP/matchup leaf. **v16** adds setup/hazard/recovery/status bonuses and
v14 tactical overrides before the matrix. **v17** is v16 plus +0.15 on v14’s action.


## Headline

| agent                            |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   search_fire_%_turns |   search_moves / game |   search_switches / game |   search_diff / game |   override_%_of_search |   ko_checks / game |   endgame / game |   loop_guards / game |   setup / game |   hazards / game |   tera / game |
|:---------------------------------|--------:|-------------:|----------:|------------:|------------:|----------------------:|----------------------:|-------------------------:|---------------------:|-----------------------:|-------------------:|-----------------:|---------------------:|---------------:|-----------------:|--------------:|
| v15 maximin (HP leaf)            |  253000 |      53.7992 |  0.19427  |     18.8113 |     1.28317 |               17.6447 |               3.47385 |                 0.978087 |              2.80423 |                66.54   |            14.3307 |        0.0253043 |             0.276763 |       0.207024 |        0.0493953 |      0.39596  |
| v16 maximin (positional bonuses) |  253000 |      54.3004 |  0.194111 |     19.025  |     1.29128 |               17.5851 |               3.61528 |                 0.945095 |              2.94362 |                67.2809 |            14.3325 |        0.0261186 |             0.259261 |       0.213075 |        0.0442569 |      0.390372 |
| v17 hybrid (v14 prior +0.15)     |  253000 |      57.8885 |  0.192393 |     18.7957 |     1.38682 |               16.2934 |               3.13733 |                 1.05194  |              1.65103 |                36.6233 |            14.4882 |        0.0261818 |             0.335549 |       0.208775 |        0.0427589 |      0.380336 |

## 1-ply vs the heuristic

- Search only runs on **~16–18% of turns**; the rest are guaranteed-KO short-circuits
  (~14 KO checks / game). One-ply maximin is a backup, not the default policy.
- Of the turns that *do* reach the matrix, **v15/v16 override v14 on ~67%** of
  decisions. Losers override more than winners (search_diff/turn 0.13 vs 0.10).
- **v16’s positional leaf is close to v15**: overall +0.5 pp vs v15, H2H ~50%, setup
  uses stay at 0.21 (v14-like). The 1.5× opponent-damage term dominates
  the 0.25–0.35 setup/hazard bonuses.
- **v17 overrides on 37%** of search decisions (prior +0.15) and is the strongest
  1-ply agent (overall +4.1 pp vs v15). Still below v12 (40.9% vs v12) and below
  its teacher (43.6% vs v14).

## Head-to-head

| file       |   games |   win_rate_% |   ci95_pp |   search_diff / game |   override_% |   search_fire_% |
|:-----------|--------:|-------------:|----------:|---------------------:|-------------:|----------------:|
| v15_vs_v16 |   10000 |        49.28 |  0.97971  |               2.9767 |      64.3899 |         18.1683 |
| v15_vs_v17 |   10000 |        45.34 |  0.975549 |               2.9521 |      64.3204 |         18.4643 |
| v16_vs_v15 |   10000 |        51.14 |  0.979557 |               3.1373 |      65.8252 |         18.1348 |
| v16_vs_v17 |   10000 |        45.68 |  0.976149 |               3.1816 |      64.9731 |         18.6096 |
| v17_vs_v15 |   10000 |        54.71 |  0.975457 |               1.8163 |      38.0473 |         17.0653 |
| v17_vs_v16 |   10000 |        54.3  |  0.976183 |               1.893  |      37.6868 |         17.2371 |

## Discriminating matchups (WR %)

| opponent         | paradigm   |   v15_wr |   v15_ci |   v15_n |   v16_wr |   v16_ci |   v16_n |   v17_wr |   v17_ci |   v17_n |
|:-----------------|:-----------|---------:|---------:|--------:|---------:|---------:|--------:|---------:|---------:|--------:|
| v12              | Heuristic  |    36.04 | 0.940863 |   10000 |    35.92 | 0.940176 |   10000 |    40.94 | 0.963599 |   10000 |
| v13              | Heuristic  |    32.82 | 0.920181 |   10000 |    33.5  | 0.924945 |   10000 |    35.1  | 0.935312 |   10000 |
| v14              | Heuristic  |    39.43 | 0.957676 |   10000 |    39.56 | 0.958224 |   10000 |    43.61 | 0.97178  |   10000 |
| abyssal          | Baseline   |    41.72 | 0.966289 |   10000 |    41.86 | 0.966745 |   10000 |    46.79 | 0.977791 |   10000 |
| simple_heuristic | Baseline   |    41.23 | 0.964628 |   10000 |    40.65 | 0.962535 |   10000 |    46.75 | 0.977741 |   10000 |
| v18              | MCTS       |    49.3  | 3.09279  |    1000 |    51.8  | 3.0911   |    1000 |    52.9  | 3.08791  |    1000 |
| v20              | MCTS       |    39.7  | 3.02701  |    1000 |    44.6  | 3.07507  |    1000 |    50.4  | 3.093    |    1000 |
| v21              | IL Hybrid  |    43.65 | 0.971881 |   10000 |    44.75 | 0.974398 |   10000 |    47.5  | 0.978587 |   10000 |
| v22              | IL Pure    |    69.67 | 0.900839 |   10000 |    70.22 | 0.896152 |   10000 |    71.27 | 0.886773 |   10000 |

## Paradigm win rates

| opponent_paradigm   |   v15_games |   v15_wins |   v15_win_rate |   v15_ci95 |   v16_games |   v16_wins |   v16_win_rate |   v16_ci95 |   v17_games |   v17_wins |   v17_win_rate |   v17_ci95 |
|:--------------------|------------:|-----------:|---------------:|-----------:|------------:|-----------:|---------------:|-----------:|------------:|-----------:|---------------:|-----------:|
| Baseline            |       60000 |      38940 |        64.9    |   0.381895 |       60000 |      38934 |        64.89   |   0.38192  |       60000 |      40929 |        68.215  |   0.37258  |
| Heuristic           |      140000 |      69972 |        49.98   |   0.261912 |      140000 |      70780 |        50.5571 |   0.261896 |      140000 |      76162 |        54.4014 |   0.260896 |
| Minimax             |       30000 |      14454 |        48.18   |   0.565392 |       30000 |      14679 |        48.93   |   0.565637 |       30000 |      15913 |        53.0433 |   0.564718 |
| MCTS                |        3000 |       1414 |        47.1333 |   1.78515  |        3000 |       1490 |        49.6667 |   1.78804  |        3000 |       1577 |        52.5667 |   1.78573  |
| IL Hybrid           |       10000 |       4365 |        43.65   |   0.971881 |       10000 |       4475 |        44.75   |   0.974398 |       10000 |       4750 |        47.5    |   0.978587 |
| IL Pure             |       10000 |       6967 |        69.67   |   0.900839 |       10000 |       7022 |        70.22   |   0.896152 |       10000 |       7127 |        71.27   |   0.886773 |

## Figures

- `minimax_fingerprint_bars.png`
- `minimax_override.png`
- `minimax_future_proxies.png`
- `minimax_winrate_grouped.png`
- `minimax_wr_by_paradigm.png`
- `minimax_key_matchups.png`
- `minimax_switching_box.png`
- `minimax_length_hp.png`