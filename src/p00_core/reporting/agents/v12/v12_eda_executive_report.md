# Executive EDA Report: Heuristic Agent `v12`

## 1. Executive Summary
- **Target Agent**: `v12`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 69.01%
- **Best Matchup**: `random` (98.62% ± 0.23%)
- **Worst Matchup**: `v12` (50.11% ± 0.98%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 76.91% | 17.99 | 2.12 | 1.40 vs 2.49 |
| **Heuristic (Basic)** | 60,000.0 | 75.83% | 17.14 | 1.73 | 1.29 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 65.77% | 17.59 | 1.26 | 1.38 vs 1.63 |
| **Heuristic (Tactical)** | 20,000.0 | 64.55% | 17.61 | 1.22 | 1.37 vs 1.57 |
| **Heuristic (Tera)** | 10,000.0 | 50.11% | 18.08 | 0.68 | 1.44 vs 1.52 |
| **Heuristic (Advanced)** | 10,000.0 | 50.65% | 18.96 | -0.05 | 1.53 vs 3.88 |
| **Heuristic (Prediction)** | 10,000.0 | 56.01% | 18.28 | 0.26 | 1.41 vs 2.37 |
| **Minimax Search** | 20,000.0 | 63.63% | 18.59 | 0.73 | 1.37 vs 2.23 |
| **MCTS Search** | 11,000.0 | 60.89% | 18.62 | 0.56 | 1.38 vs 2.33 |
| **Imitation Learning** | 12,000.0 | 59.52% | 17.97 | 0.51 | 1.39 vs 2.20 |
| **Pure Imitation** | 10,000.0 | 80.79% | 18.70 | 2.00 | 1.35 vs 3.76 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 98.62% | ±0.23% | 21.19 | 4.28 | 0.02 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 90.27% | ±0.58% | 17.21 | 2.78 | 0.09 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 80.79% | ±0.77% | 18.70 | 2.35 | 0.35 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 76.48% | ±0.83% | 16.99 | 1.99 | 0.23 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 76.45% | ±0.83% | 16.95 | 1.99 | 0.23 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 76.35% | ±0.83% | 17.16 | 1.98 | 0.24 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 76.33% | ±0.83% | 17.04 | 1.98 | 0.24 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 76.09% | ±0.84% | 17.13 | 1.99 | 0.24 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 75.81% | ±0.84% | 17.21 | 1.96 | 0.24 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 75.53% | ±0.84% | 17.14 | 1.98 | 0.25 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 74.87% | ±0.85% | 17.15 | 1.94 | 0.25 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 68.48% | ±0.91% | 17.52 | 1.70 | 0.37 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 67.44% | ±0.92% | 17.56 | 1.65 | 0.38 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 67.30% | ±0.92% | 17.61 | 1.65 | 0.39 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 66.10% | ±2.93% | 18.16 | 1.61 | 0.67 | ⚠️ N=1k (high variance) |
| `v19` | Imitation Learning | 1,000 | 64.50% | ±2.97% | 18.54 | 1.54 | 0.70 | ⚠️ N=1k (high variance) |
| `v15` | Minimax Search | 10,000 | 63.96% | ±0.94% | 18.40 | 1.53 | 0.77 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 63.30% | ±0.94% | 18.78 | 1.49 | 0.79 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 61.65% | ±0.95% | 17.65 | 1.61 | 0.44 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 61.52% | ±0.95% | 17.63 | 1.62 | 0.45 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 60.37% | ±0.96% | 18.66 | 1.36 | 0.84 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 59.91% | ±0.96% | 17.79 | 1.59 | 0.46 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 59.75% | ±0.96% | 17.80 | 1.61 | 0.46 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 59.12% | ±0.96% | 17.92 | 1.31 | 0.83 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 58.50% | ±3.05% | 17.84 | 1.31 | 0.89 | ⚠️ N=1k (high variance) |
| `v14` | Heuristic (Prediction) | 10,000 | 56.01% | ±0.97% | 18.28 | 1.23 | 0.97 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 50.65% | ±0.98% | 18.96 | 1.32 | 1.37 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 50.11% | ±0.98% | 18.08 | 1.26 | 0.57 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
