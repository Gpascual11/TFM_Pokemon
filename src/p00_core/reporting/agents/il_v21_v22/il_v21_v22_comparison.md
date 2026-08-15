# Imitation Learning EDA — v21 hybrid vs v22

Source: `data/benchmarks/all_10k/gen9randombattle` (each agent as us vs 28 opponents).

## Architecture in one paragraph

Both share the 1,150-feature XGBoost **macro** model (move vs switch, τ = 0.5525).
**v21** is a hybrid: v14 KO/endgame/setup run *before* XGBoost; remaining execution is
still v14. **v22** uses the same macro head, then a second XGBoost that scores candidate
moves from attributes (power, STAB, effectiveness), plus loop-guard / Tera heuristics.


## Headline

| agent                  |   games |   win_rate_% |   ci95_pp |   avg_turns |   avg_hp_us |   vol_switches |   xgb_fire_%_turns |   xgb_switch_share_% |   mean_p_switch |   ko_guards / game |   endgame / game |   loop_guards / game |   fallback / game |   error / game |
|:-----------------------|--------:|-------------:|----------:|------------:|------------:|---------------:|-------------------:|---------------------:|----------------:|-------------------:|-----------------:|---------------------:|------------------:|---------------:|
| v21 Hybrid (XGB + v14) |  253000 |      58.7075 |  0.191856 |     18.2042 |    1.33134  |        1.97813 |            15.2183 |              35.5475 |       0.0798704 |            13.8473 |         0.031751 |             0.381534 |         0         |              0 |
| v22 Pure IL (two XGBs) |  253000 |      33.4925 |  0.183909 |     20.0688 |    0.703403 |        3.72474 |            79.9134 |              15.1899 |       0.351111  |             0      |         0        |             1.9196   |         0.0112727 |              0 |

## Fingerprint (mean per game)

|                   |        v21 |        v22 |
|:------------------|-----------:|-----------:|
| ko_guards_us      | 13.8473    |  0         |
| endgame_solves_us |  0.031751  |  0         |
| ko_checks_us      |  0.631166  |  0         |
| search_moves_us   |  0         |  0         |
| xgb_stays_us      |  2.66781   | 17.1909    |
| xgb_switches_us   |  0.969253  |  2.87537   |
| loop_guards_us    |  0.381534  |  1.9196    |
| fallback_moves_us |  0         |  0.0112727 |
| xgb_fire_rate     |  0.152183  |  0.799134  |
| p_switch_mean     |  0.0798704 |  0.351111  |

## Head-to-head

| file       |   games |   win_rate_% |   ci95_pp |   avg_turns |   xgb_switch_share_% |   endgame / game |   ko_guards / game |
|:-----------|--------:|-------------:|----------:|------------:|---------------------:|-----------------:|-------------------:|
| v21_vs_v22 |   10000 |        71.74 |  0.882387 |     19.3704 |              33.2879 |           0.0243 |            15.1302 |
| v22_vs_v21 |   10000 |        29.07 |  0.889873 |     19.3644 |              14.8782 |           0      |             0      |

Reciprocal sum = 1.0081

## Matchup notes

- v21 best: `random` (98.5%)
- v21 worst: `v13` (38.4%)
- v22 best: `random` (96.6%)
- v22 worst: `v12` (19.8%)
- Largest |WR gap|: `safe_one_step` (v21 − v22 = +32.6 pp)
- v21 ahead in 28 / 28 opponents (mean Δ +25.24 pp)

## Paradigm win rates

| opponent_paradigm   |   v21_games |   v21_wins |   v21_win_rate |   v21_ci95 |   v22_games |   v22_wins |   v22_win_rate |   v22_ci95 |   delta_pp |
|:--------------------|------------:|-----------:|---------------:|-----------:|------------:|-----------:|---------------:|-----------:|-----------:|
| Baseline            |       60000 |      41251 |        68.7517 |   0.370872 |       60000 |      26852 |        44.7533 |   0.397862 |    23.9983 |
| Heuristic           |      140000 |      76966 |        54.9757 |   0.260612 |      140000 |      40158 |        28.6843 |   0.23692  |    26.2914 |
| Minimax             |       30000 |      16542 |        55.14   |   0.56277  |       30000 |       9021 |        30.07   |   0.518885 |    25.07   |
| MCTS                |        3000 |       1605 |        53.5    |   1.7837   |        3000 |        840 |        28      |   1.60594  |    25.5    |
| IL Hybrid           |       10000 |       4992 |        49.92   |   0.979811 |       10000 |       2907 |        29.07   |   0.889873 |    20.85   |
| IL Pure             |       10000 |       7174 |        71.74   |   0.882387 |       10000 |       4958 |        49.58   |   0.979777 |    22.16   |

## Figures

- `il_fingerprint_bars.png`
- `il_policy_firing.png`
- `il_winrate_grouped.png`
- `il_switching_box.png`
- `il_tactical_proxies.png`
- `il_wr_by_paradigm.png`
- `il_wr_scatter.png`
- `il_length_hp.png`