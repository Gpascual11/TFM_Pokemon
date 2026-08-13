# Executive EDA Report: Heuristic Agent `v2`

## 1. Executive Summary
- **Target Agent**: `v2`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 44.70%
- **Best Matchup**: `random` (97.34% ± 0.32%)
- **Worst Matchup**: `v12` (24.05% ± 0.84%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 56.77% | 18.87 | 0.94 | 1.04 vs 2.66 |
| **Heuristic (Basic)** | 60,000.0 | 49.58% | 17.55 | 0.39 | 1.02 vs 1.11 |
| **Heuristic (Strategic)** | 30,000.0 | 36.40% | 17.22 | -0.10 | 1.02 vs 1.46 |
| **Heuristic (Tactical)** | 20,000.0 | 36.07% | 17.23 | -0.10 | 1.02 vs 1.41 |
| **Heuristic (Tera)** | 10,000.0 | 24.05% | 17.09 | -0.44 | 1.02 vs 1.36 |
| **Heuristic (Advanced)** | 10,000.0 | 27.25% | 17.97 | -1.60 | 1.02 vs 3.16 |
| **Heuristic (Prediction)** | 10,000.0 | 32.56% | 17.71 | -1.02 | 1.01 vs 2.11 |
| **Minimax Search** | 20,000.0 | 40.03% | 18.43 | -0.69 | 1.02 vs 2.22 |
| **MCTS Search** | 11,000.0 | 35.53% | 18.04 | -0.90 | 1.01 vs 2.23 |
| **Imitation Learning** | 12,000.0 | 35.32% | 17.50 | -0.83 | 1.01 vs 2.09 |
| **Pure Imitation** | 10,000.0 | 66.19% | 19.73 | 0.77 | 1.04 vs 3.95 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.34% | ±0.32% | 25.09 | 3.54 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 79.87% | ±0.79% | 18.84 | 1.89 | 0.20 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 66.19% | ±0.93% | 19.73 | 1.39 | 0.63 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 50.54% | ±0.98% | 17.33 | 0.92 | 0.50 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 50.33% | ±0.98% | 17.70 | 0.92 | 0.49 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 50.28% | ±0.98% | 17.38 | 0.90 | 0.50 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 50.13% | ±0.98% | 17.55 | 0.92 | 0.50 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 49.58% | ±0.98% | 17.45 | 0.89 | 0.51 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 49.58% | ±0.98% | 17.47 | 0.90 | 0.51 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 49.10% | ±0.98% | 17.56 | 0.87 | 0.51 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 48.73% | ±0.98% | 17.56 | 0.88 | 0.52 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 40.50% | ±3.04% | 17.95 | 0.69 | 1.27 | ⚠️ N=1k (high variance) |
| `v15` | Minimax Search | 10,000 | 40.23% | ±0.96% | 18.34 | 0.67 | 1.36 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 39.84% | ±0.96% | 18.53 | 0.67 | 1.35 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 37.55% | ±0.95% | 17.31 | 0.64 | 0.72 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 37.42% | ±0.95% | 17.19 | 0.62 | 0.70 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 36.69% | ±0.94% | 17.19 | 0.61 | 0.73 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 35.55% | ±0.94% | 18.07 | 0.58 | 1.49 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 35.30% | ±2.96% | 17.76 | 0.56 | 1.37 | ⚠️ N=1k (high variance) |
| `v20` | Imitation Learning | 1,000 | 35.20% | ±2.96% | 17.67 | 0.56 | 1.47 | ⚠️ N=1k (high variance) |
| `v9` | Heuristic (Strategic) | 10,000 | 34.96% | ±0.93% | 17.17 | 0.64 | 0.75 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 34.81% | ±0.93% | 17.44 | 0.57 | 1.42 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 34.71% | ±0.93% | 17.26 | 0.63 | 0.74 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 32.56% | ±0.92% | 17.71 | 0.53 | 1.55 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 31.38% | ±0.91% | 17.36 | 0.58 | 0.77 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 31.24% | ±0.91% | 17.23 | 0.55 | 0.77 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 27.25% | ±0.87% | 17.97 | 0.50 | 2.11 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 24.05% | ±0.84% | 17.09 | 0.42 | 0.86 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
