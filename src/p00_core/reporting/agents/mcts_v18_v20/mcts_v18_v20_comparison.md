# Shallow MCTS EDA — v18 / v19 / v20

Source: `data/benchmarks/all_10k/gen9randombattle` (each agent as us vs 28 opponents, **1k games**).
Budget: 100 simulations / turn, 5-turn LocalSim rollouts, C = 1.4.

## Architecture in one paragraph

All three inherit HeuristicV14. Each iteration picks a **root** child by UCB, runs a
5-turn LocalSim rollout, and backs up that child. Hidden info is revealed moves.
**v18** UCB1 + HP-style leaf. **v19** positional leaf + v14 overrides before the tree.
**v20** PUCT prior 0.70 on the v14 action; leaves stay v19-style.


## Headline

| agent                      |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   search_fire_%_turns |   search_moves / game |   search_switches / game |   search_diff / game |   override_%_of_search |   ko_checks / game |   endgame / game |   loop_guards / game |   setup / game |   hazards / game |   tera / game |
|:---------------------------|--------:|-------------:|----------:|------------:|------------:|----------------------:|----------------------:|-------------------------:|---------------------:|-----------------------:|-------------------:|-----------------:|---------------------:|---------------:|-----------------:|--------------:|
| v18 UCB1 (HP leaf)         |   28000 |      54.0214 |  0.583725 |     18.5307 |     1.2075  |               18.0559 |               3.7565  |                 0.608107 |             3.12561  |                71.3359 |            14.1627 |        0.0333571 |             0.09825  |       0.223393 |        0.04625   |      0.405536 |
| v19 UCB1 (positional leaf) |   28000 |      53.2857 |  0.584356 |     18.5756 |     1.21621 |               17.6207 |               3.39714 |                 0.873179 |             3.07329  |                71.0974 |            14.1925 |        0.0291429 |             0.259607 |       0.21875  |        0.0468929 |      0.3935   |
| v20 PUCT (v14 prior 0.70)  |   28000 |      59.6607 |  0.574588 |     18.3269 |     1.39729 |               15.5043 |               2.60439 |                 1.06875  |             0.786714 |                18.6586 |            14.5435 |        0.0280357 |             0.346571 |       0.2015   |        0.0352857 |      0.388071 |

## Lookahead vs the heuristic

- Search only runs on **~16–18% of turns**; the rest are guaranteed-KO short-circuits
  (~14 KO checks / game). Five-ply search is a backup, not the default policy.
- Of the turns that *do* reach the tree, **v18/v19 override v14 on ~71%** of decisions.
  Losers override more than winners (search_diff/turn 0.15 vs 0.11). That is the
  horizon effect in the data: unconstrained 5-ply disagreement correlates with losing.
- **v20 overrides on only ~19%** of search decisions and is the strongest MCTS agent
  (overall +5.6 pp vs v18). PUCT is mostly re-ranking v14, not replacing it.
- Setup / hazards stay at v14 levels (~0.22 / ~0.04), not v12 levels. Five greedy
  rollout turns keep setup / hazards at v14 levels (~0.22 / ~0.04).

## Head-to-head

| file       |   games |   win_rate_% |   ci95_pp |   search_diff / game |   override_% |   search_fire_% |
|:-----------|--------:|-------------:|----------:|---------------------:|-------------:|----------------:|
| v18_vs_v19 |    1000 |         49.3 |   3.09279 |                2.848 |      71.6965 |         17.3783 |
| v18_vs_v20 |    1000 |         43.6 |   3.06775 |                2.845 |      68.2457 |         17.9522 |
| v19_vs_v18 |    1000 |         51.4 |   3.09189 |                2.831 |      71.6005 |         17.1638 |
| v19_vs_v20 |    1000 |         41.2 |   3.045   |                2.844 |      69.185  |         17.3873 |
| v20_vs_v18 |    1000 |         56.6 |   3.06614 |                0.791 |      18.9947 |         15.9905 |
| v20_vs_v19 |    1000 |         56.6 |   3.06614 |                0.827 |      19.4032 |         15.5613 |

## Discriminating matchups (WR %)

| opponent         | paradigm   |   v18_wr |   v18_ci |   v19_wr |   v19_ci |   v20_wr |   v20_ci |
|:-----------------|:-----------|---------:|---------:|---------:|---------:|---------:|---------:|
| v12              | Heuristic  |     34   |  2.93109 |     33.1 |  2.91177 |     42.7 |  3.06008 |
| v13              | Heuristic  |     28.6 |  2.79667 |     34.1 |  2.93317 |     39.1 |  3.01899 |
| v14              | Heuristic  |     40   |  3.03084 |     41.7 |  3.05035 |     47   |  3.08755 |
| abyssal          | Baseline   |     42.2 |  3.05537 |     38.7 |  3.01338 |     49   |  3.09248 |
| simple_heuristic | Baseline   |     42   |  3.0534  |     40.1 |  3.0321  |     49.2 |  3.0927  |
| v15              | Minimax    |     49.3 |  3.09279 |     51.6 |  3.09152 |     59.1 |  3.04164 |
| v17              | Minimax    |     44.7 |  3.07574 |     45.3 |  3.07945 |     55.8 |  3.0723  |
| v21              | IL Hybrid  |     44.1 |  3.07157 |     46.5 |  3.08554 |     49.6 |  3.093   |
| v22              | IL Pure    |     71.1 |  2.80535 |     66.9 |  2.91177 |     73   |  2.74783 |

## Paradigm win rates

| opponent_paradigm   |   v18_games |   v18_wins |   v18_win_rate |   v18_ci95 |   v19_games |   v19_wins |   v19_win_rate |   v19_ci95 |   v20_games |   v20_wins |   v20_win_rate |   v20_ci95 |
|:--------------------|------------:|-----------:|---------------:|-----------:|------------:|-----------:|---------------:|-----------:|------------:|-----------:|---------------:|-----------:|
| Baseline            |        6000 |       3950 |        65.8333 |   1.19972  |        6000 |       3859 |        64.3167 |   1.21185  |        6000 |       4194 |        69.9    |   1.16035  |
| Heuristic           |       14000 |       7111 |        50.7929 |   0.828033 |       14000 |       7044 |        50.3143 |   0.828121 |       14000 |       7932 |        56.6571 |   0.820767 |
| Minimax             |        3000 |       1461 |        48.7    |   1.78748  |        3000 |       1462 |        48.7333 |   1.78751  |        3000 |       1722 |        57.4    |   1.76842  |
| MCTS                |        3000 |       1452 |        48.4    |   1.78717  |        3000 |       1421 |        47.3667 |   1.7856   |        3000 |       1631 |        54.3667 |   1.78126  |
| IL Hybrid           |        1000 |        441 |        44.1    |   3.07157  |        1000 |        465 |        46.5    |   3.08554  |        1000 |        496 |        49.6    |   3.093    |
| IL Pure             |        1000 |        711 |        71.1    |   2.80535  |        1000 |        669 |        66.9    |   2.91177  |        1000 |        730 |        73      |   2.74783  |

## Figures

- `mcts_fingerprint_bars.png`
- `mcts_override.png`
- `mcts_future_proxies.png`
- `mcts_winrate_grouped.png`
- `mcts_wr_by_paradigm.png`
- `mcts_key_matchups.png`
- `mcts_switching_box.png`
- `mcts_length_hp.png`