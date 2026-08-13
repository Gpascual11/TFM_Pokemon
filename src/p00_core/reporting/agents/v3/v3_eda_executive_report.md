# Executive EDA Report: Heuristic Agent `v3`

## 1. Executive Summary
- **Target Agent**: `v3`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 44.75%
- **Best Matchup**: `random` (97.12% ± 0.33%)
- **Worst Matchup**: `v12` (24.40% ± 0.84%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 56.67% | 18.87 | 0.93 | 1.04 vs 2.67 |
| **Heuristic (Basic)** | 60,000.0 | 49.62% | 17.52 | 0.40 | 1.02 vs 1.11 |
| **Heuristic (Strategic)** | 30,000.0 | 37.41% | 17.28 | -0.07 | 1.02 vs 1.46 |
| **Heuristic (Tactical)** | 20,000.0 | 35.94% | 17.22 | -0.10 | 1.02 vs 1.42 |
| **Heuristic (Tera)** | 10,000.0 | 24.40% | 17.10 | -0.44 | 1.02 vs 1.37 |
| **Heuristic (Advanced)** | 10,000.0 | 26.30% | 17.93 | -1.66 | 1.02 vs 3.18 |
| **Heuristic (Prediction)** | 10,000.0 | 32.42% | 17.77 | -1.01 | 1.01 vs 2.12 |
| **Minimax Search** | 20,000.0 | 39.65% | 18.39 | -0.72 | 1.02 vs 2.23 |
| **MCTS Search** | 11,000.0 | 36.44% | 18.13 | -0.85 | 1.02 vs 2.22 |
| **Imitation Learning** | 12,000.0 | 35.40% | 17.51 | -0.82 | 1.02 vs 2.09 |
| **Pure Imitation** | 10,000.0 | 65.29% | 19.68 | 0.74 | 1.04 vs 3.95 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.12% | ±0.33% | 25.05 | 3.56 | 0.04 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 79.97% | ±0.78% | 18.81 | 1.89 | 0.20 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 65.29% | ±0.93% | 19.68 | 1.39 | 0.65 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 50.94% | ±0.98% | 17.52 | 0.93 | 0.50 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 50.82% | ±0.98% | 17.50 | 0.93 | 0.49 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 50.59% | ±0.98% | 17.35 | 0.90 | 0.50 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 49.85% | ±0.98% | 17.55 | 0.91 | 0.50 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 49.81% | ±0.98% | 17.35 | 0.90 | 0.50 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 48.90% | ±0.98% | 17.56 | 0.89 | 0.51 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 48.76% | ±0.98% | 17.59 | 0.89 | 0.52 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 48.47% | ±0.98% | 17.40 | 0.87 | 0.52 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 40.30% | ±3.04% | 17.97 | 0.69 | 1.27 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 39.79% | ±0.96% | 18.42 | 0.66 | 1.38 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 39.70% | ±3.03% | 17.98 | 0.65 | 1.29 | ⚠️ N=1k (high variance) |
| `v15` | Minimax Search | 10,000 | 39.50% | ±0.96% | 18.36 | 0.66 | 1.37 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 38.60% | ±0.95% | 17.34 | 0.66 | 0.71 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 38.18% | ±0.95% | 17.26 | 0.64 | 0.71 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 37.65% | ±0.95% | 17.25 | 0.62 | 0.71 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 36.11% | ±0.94% | 18.14 | 0.59 | 1.46 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 35.45% | ±0.94% | 17.23 | 0.64 | 0.74 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 35.40% | ±2.96% | 17.30 | 0.59 | 1.51 | ⚠️ N=1k (high variance) |
| `v21` | Imitation Learning | 10,000 | 34.91% | ±0.93% | 17.48 | 0.57 | 1.41 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 34.23% | ±0.93% | 17.19 | 0.62 | 0.74 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 32.42% | ±0.92% | 17.77 | 0.53 | 1.54 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 31.51% | ±0.91% | 17.42 | 0.58 | 0.77 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 31.05% | ±0.91% | 17.28 | 0.56 | 0.78 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 26.30% | ±0.86% | 17.93 | 0.48 | 2.14 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 24.40% | ±0.84% | 17.10 | 0.42 | 0.86 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
