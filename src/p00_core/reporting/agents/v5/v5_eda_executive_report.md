# Executive EDA Report: Heuristic Agent `v5`

## 1. Executive Summary
- **Target Agent**: `v5`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 45.86%
- **Best Matchup**: `random` (97.57% ± 0.30%)
- **Worst Matchup**: `v12` (24.78% ± 0.85%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 57.32% | 18.79 | 0.97 | 1.04 vs 2.67 |
| **Heuristic (Basic)** | 60,000.0 | 51.14% | 17.46 | 0.44 | 1.02 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 38.40% | 17.29 | -0.04 | 1.02 vs 1.47 |
| **Heuristic (Tactical)** | 20,000.0 | 37.28% | 17.21 | -0.06 | 1.02 vs 1.41 |
| **Heuristic (Tera)** | 10,000.0 | 24.78% | 17.08 | -0.42 | 1.02 vs 1.37 |
| **Heuristic (Advanced)** | 10,000.0 | 27.50% | 18.05 | -1.60 | 1.02 vs 3.17 |
| **Heuristic (Prediction)** | 10,000.0 | 33.31% | 17.78 | -0.97 | 1.01 vs 2.10 |
| **Minimax Search** | 20,000.0 | 41.27% | 18.43 | -0.61 | 1.02 vs 2.23 |
| **MCTS Search** | 11,000.0 | 36.89% | 18.20 | -0.80 | 1.01 vs 2.25 |
| **Imitation Learning** | 12,000.0 | 36.58% | 17.43 | -0.76 | 1.01 vs 2.09 |
| **Pure Imitation** | 10,000.0 | 67.26% | 19.78 | 0.82 | 1.03 vs 3.97 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.57% | ±0.30% | 25.02 | 3.57 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 80.48% | ±0.78% | 18.68 | 1.95 | 0.19 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 67.26% | ±0.92% | 19.78 | 1.44 | 0.62 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 52.07% | ±0.98% | 17.56 | 0.94 | 0.48 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 51.78% | ±0.98% | 17.47 | 0.94 | 0.48 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 51.21% | ±0.98% | 17.23 | 0.93 | 0.49 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 51.10% | ±0.98% | 17.43 | 0.94 | 0.49 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 51.08% | ±0.98% | 17.51 | 0.93 | 0.50 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 51.01% | ±0.98% | 17.24 | 0.92 | 0.49 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 50.69% | ±0.98% | 17.46 | 0.93 | 0.49 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 50.11% | ±0.98% | 17.32 | 0.91 | 0.51 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 41.49% | ±0.97% | 18.33 | 0.70 | 1.30 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 41.40% | ±3.05% | 17.81 | 0.71 | 1.25 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 41.05% | ±0.96% | 18.54 | 0.69 | 1.31 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 40.80% | ±3.05% | 17.79 | 0.76 | 1.25 | ⚠️ N=1k (high variance) |
| `v7` | Heuristic (Strategic) | 10,000 | 40.10% | ±0.96% | 17.42 | 0.69 | 0.69 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 39.47% | ±0.96% | 17.25 | 0.66 | 0.68 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 38.74% | ±0.95% | 17.23 | 0.66 | 0.70 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 36.55% | ±0.94% | 17.39 | 0.61 | 1.37 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 36.44% | ±0.94% | 18.23 | 0.61 | 1.44 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 36.36% | ±0.94% | 17.23 | 0.66 | 0.74 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 35.08% | ±0.94% | 17.17 | 0.64 | 0.73 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 33.31% | ±0.92% | 17.78 | 0.55 | 1.52 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 32.70% | ±2.91% | 17.46 | 0.55 | 1.50 | ⚠️ N=1k (high variance) |
| `abyssal` | Baseline | 10,000 | 32.50% | ±0.92% | 17.33 | 0.60 | 0.77 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 31.13% | ±0.91% | 17.27 | 0.58 | 0.77 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 27.50% | ±0.88% | 18.05 | 0.50 | 2.09 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 24.78% | ±0.85% | 17.08 | 0.43 | 0.86 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
