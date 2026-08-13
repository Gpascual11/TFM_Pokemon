# Executive EDA Report: Heuristic Agent `v10`

## 1. Executive Summary
- **Target Agent**: `v10`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 55.66%
- **Best Matchup**: `random` (97.70% ± 0.29%)
- **Worst Matchup**: `v12` (33.22% ± 0.92%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 65.61% | 18.39 | 1.35 | 1.45 vs 2.61 |
| **Heuristic (Basic)** | 60,000.0 | 62.13% | 17.18 | 0.87 | 1.33 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 49.31% | 17.44 | 0.35 | 1.42 vs 1.56 |
| **Heuristic (Tactical)** | 20,000.0 | 47.62% | 17.40 | 0.32 | 1.42 vs 1.51 |
| **Heuristic (Tera)** | 10,000.0 | 33.22% | 17.61 | -0.15 | 1.49 vs 1.48 |
| **Heuristic (Advanced)** | 10,000.0 | 34.60% | 18.77 | -1.11 | 1.57 vs 3.65 |
| **Heuristic (Prediction)** | 10,000.0 | 43.61% | 18.22 | -0.42 | 1.51 vs 2.29 |
| **Minimax Search** | 20,000.0 | 52.26% | 18.60 | -0.04 | 1.46 vs 2.22 |
| **MCTS Search** | 11,000.0 | 48.27% | 18.37 | -0.21 | 1.44 vs 2.25 |
| **Imitation Learning** | 12,000.0 | 47.30% | 17.76 | -0.20 | 1.45 vs 2.16 |
| **Pure Imitation** | 10,000.0 | 72.70% | 19.20 | 1.23 | 1.45 vs 3.86 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.70% | ±0.29% | 23.59 | 3.85 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 87.20% | ±0.65% | 17.73 | 2.31 | 0.13 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 72.70% | ±0.87% | 19.20 | 1.71 | 0.48 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 62.97% | ±0.95% | 17.12 | 1.28 | 0.37 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 62.69% | ±0.95% | 17.21 | 1.26 | 0.38 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 62.60% | ±0.95% | 17.24 | 1.27 | 0.38 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 62.17% | ±0.95% | 16.95 | 1.26 | 0.38 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 62.02% | ±0.95% | 16.97 | 1.24 | 0.38 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 61.96% | ±0.95% | 17.22 | 1.24 | 0.38 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 61.46% | ±0.95% | 17.13 | 1.24 | 0.39 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 61.11% | ±0.96% | 17.13 | 1.23 | 0.39 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 52.82% | ±0.98% | 18.48 | 0.97 | 0.97 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 51.71% | ±0.98% | 18.73 | 0.94 | 1.02 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 51.70% | ±3.10% | 18.21 | 0.94 | 0.96 | ⚠️ N=1k (high variance) |
| `v18` | MCTS Search | 1,000 | 51.50% | ±3.10% | 17.99 | 0.98 | 0.98 | ⚠️ N=1k (high variance) |
| `v7` | Heuristic (Strategic) | 10,000 | 50.68% | ±0.98% | 17.47 | 0.95 | 0.57 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 50.55% | ±0.98% | 17.37 | 0.93 | 0.58 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 49.29% | ±0.98% | 17.32 | 0.91 | 0.57 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 47.95% | ±0.98% | 18.41 | 0.88 | 1.11 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 47.26% | ±0.98% | 17.69 | 0.86 | 1.05 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 46.69% | ±0.98% | 17.49 | 0.93 | 0.62 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 45.94% | ±0.98% | 17.47 | 0.91 | 0.62 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 43.61% | ±0.97% | 18.22 | 0.79 | 1.21 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 43.30% | ±3.07% | 18.02 | 0.78 | 1.17 | ⚠️ N=1k (high variance) |
| `simple_heuristic` | Baseline | 10,000 | 42.70% | ±0.97% | 17.68 | 0.85 | 0.66 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 41.86% | ±0.97% | 17.41 | 0.83 | 0.67 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 34.60% | ±0.93% | 18.77 | 0.68 | 1.78 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 33.22% | ±0.92% | 17.61 | 0.62 | 0.78 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
