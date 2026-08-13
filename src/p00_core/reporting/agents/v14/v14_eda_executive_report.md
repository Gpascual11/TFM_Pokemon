# Executive EDA Report: Heuristic Agent `v14`

## 1. Executive Summary
- **Target Agent**: `v14`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 62.03%
- **Best Matchup**: `random` (98.63% ± 0.23%)
- **Worst Matchup**: `v13` (41.60% ± 0.97%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 71.06% | 18.43 | 1.60 | 2.09 vs 2.48 |
| **Heuristic (Basic)** | 60,000.0 | 67.16% | 17.72 | 1.00 | 1.95 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 56.93% | 18.26 | 0.43 | 2.12 vs 1.64 |
| **Heuristic (Tactical)** | 20,000.0 | 55.18% | 18.25 | 0.35 | 2.11 vs 1.59 |
| **Heuristic (Tera)** | 10,000.0 | 44.74% | 18.38 | -0.27 | 2.22 vs 1.52 |
| **Heuristic (Advanced)** | 10,000.0 | 41.60% | 20.34 | -0.57 | 2.32 vs 3.98 |
| **Heuristic (Prediction)** | 10,000.0 | 49.69% | 19.52 | -0.02 | 2.21 vs 2.40 |
| **Minimax Search** | 20,000.0 | 59.70% | 19.40 | 0.46 | 2.16 vs 2.13 |
| **MCTS Search** | 11,000.0 | 56.98% | 19.38 | 0.31 | 2.17 vs 2.19 |
| **Imitation Learning** | 12,000.0 | 54.94% | 18.88 | 0.27 | 2.19 vs 2.20 |
| **Pure Imitation** | 10,000.0 | 74.87% | 19.55 | 1.44 | 2.03 vs 3.75 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 98.63% | ±0.23% | 21.22 | 4.07 | 0.02 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 90.75% | ±0.57% | 17.49 | 2.71 | 0.09 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 74.87% | ±0.85% | 19.55 | 1.88 | 0.45 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 68.15% | ±0.91% | 17.75 | 1.54 | 0.52 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 67.76% | ±0.92% | 17.73 | 1.55 | 0.52 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 67.55% | ±0.92% | 17.53 | 1.54 | 0.33 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 67.41% | ±0.92% | 17.67 | 1.55 | 0.53 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 67.39% | ±0.92% | 17.62 | 1.54 | 0.54 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 67.07% | ±0.92% | 17.72 | 1.55 | 0.54 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 66.90% | ±0.92% | 17.76 | 1.54 | 0.54 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 65.67% | ±0.93% | 17.71 | 1.49 | 0.56 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 60.07% | ±0.96% | 19.29 | 1.29 | 0.81 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 59.80% | ±3.04% | 18.67 | 1.27 | 0.81 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 59.34% | ±0.96% | 19.51 | 1.26 | 0.82 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 58.90% | ±0.96% | 18.31 | 1.27 | 0.74 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 58.20% | ±3.06% | 18.89 | 1.28 | 0.85 | ⚠️ N=1k (high variance) |
| `v8` | Heuristic (Strategic) | 10,000 | 57.87% | ±0.97% | 18.21 | 1.23 | 0.77 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 56.76% | ±0.97% | 18.25 | 1.21 | 0.78 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 56.70% | ±0.97% | 19.45 | 1.18 | 0.88 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 54.74% | ±0.98% | 18.88 | 1.14 | 0.87 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 54.01% | ±0.98% | 18.27 | 1.24 | 0.94 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 53.70% | ±3.09% | 18.81 | 1.13 | 0.92 | ⚠️ N=1k (high variance) |
| `v11` | Heuristic (Tactical) | 10,000 | 53.60% | ±0.98% | 18.26 | 1.21 | 0.94 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 51.36% | ±0.98% | 18.32 | 1.16 | 0.55 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 50.66% | ±0.98% | 18.37 | 1.15 | 1.05 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 49.69% | ±0.98% | 19.52 | 1.03 | 1.05 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 44.74% | ±0.97% | 18.38 | 0.97 | 1.24 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 41.60% | ±0.97% | 20.34 | 0.94 | 1.50 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
