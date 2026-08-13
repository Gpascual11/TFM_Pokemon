# Executive EDA Report: Heuristic Agent `v1`

## 1. Executive Summary
- **Target Agent**: `v1`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 44.25%
- **Best Matchup**: `random` (97.53% ± 0.30%)
- **Worst Matchup**: `v12` (23.29% ± 0.83%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 56.23% | 18.91 | 0.92 | 1.02 vs 2.68 |
| **Heuristic (Basic)** | 60,000.0 | 48.80% | 17.54 | 0.36 | 1.01 vs 1.11 |
| **Heuristic (Strategic)** | 30,000.0 | 37.17% | 17.27 | -0.08 | 1.01 vs 1.45 |
| **Heuristic (Tactical)** | 20,000.0 | 35.44% | 17.25 | -0.12 | 1.01 vs 1.40 |
| **Heuristic (Tera)** | 10,000.0 | 23.29% | 17.12 | -0.47 | 1.01 vs 1.37 |
| **Heuristic (Advanced)** | 10,000.0 | 27.38% | 17.95 | -0.86 | 1.00 vs 3.15 |
| **Heuristic (Prediction)** | 10,000.0 | 32.09% | 17.81 | -0.81 | 1.00 vs 2.11 |
| **Minimax Search** | 20,000.0 | 38.98% | 18.44 | -0.75 | 1.00 vs 2.25 |
| **MCTS Search** | 11,000.0 | 35.96% | 18.10 | -0.88 | 1.00 vs 2.25 |
| **Imitation Learning** | 12,000.0 | 34.04% | 17.41 | -0.88 | 1.00 vs 2.09 |
| **Pure Imitation** | 10,000.0 | 65.72% | 19.73 | 0.76 | 1.00 vs 3.95 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.53% | ±0.30% | 25.35 | 3.54 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 80.21% | ±0.78% | 18.77 | 1.90 | 0.19 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 65.72% | ±0.93% | 19.73 | 1.40 | 0.64 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 50.44% | ±0.98% | 17.63 | 0.91 | 0.49 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 49.93% | ±0.98% | 17.42 | 0.90 | 0.50 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 49.12% | ±0.98% | 17.52 | 0.89 | 0.51 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 49.08% | ±0.98% | 17.55 | 0.89 | 0.51 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 48.83% | ±0.98% | 17.25 | 0.87 | 0.51 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 48.81% | ±0.98% | 17.53 | 0.88 | 0.51 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 47.75% | ±0.98% | 17.48 | 0.86 | 0.53 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 47.59% | ±0.98% | 17.56 | 0.84 | 0.53 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 39.23% | ±0.96% | 18.37 | 0.64 | 1.39 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 38.97% | ±0.96% | 17.31 | 0.66 | 0.70 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 38.74% | ±0.95% | 18.51 | 0.64 | 1.39 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 37.80% | ±3.01% | 17.59 | 0.62 | 1.34 | ⚠️ N=1k (high variance) |
| `v8` | Heuristic (Strategic) | 10,000 | 37.40% | ±0.95% | 17.19 | 0.63 | 0.72 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 36.52% | ±0.94% | 17.22 | 0.60 | 0.71 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 36.50% | ±2.98% | 17.96 | 0.61 | 1.32 | ⚠️ N=1k (high variance) |
| `v17` | MCTS Search | 10,000 | 35.91% | ±0.94% | 18.11 | 0.59 | 1.49 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 35.14% | ±0.94% | 17.30 | 0.64 | 0.75 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 34.35% | ±0.93% | 17.28 | 0.61 | 0.74 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 34.19% | ±0.93% | 17.39 | 0.56 | 1.43 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 32.09% | ±0.91% | 17.81 | 0.52 | 1.33 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 30.64% | ±0.90% | 17.33 | 0.55 | 0.79 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 30.26% | ±0.90% | 17.33 | 0.57 | 0.79 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 28.80% | ±2.81% | 17.33 | 0.47 | 1.55 | ⚠️ N=1k (high variance) |
| `v13` | Heuristic (Advanced) | 10,000 | 27.38% | ±0.87% | 17.95 | 0.49 | 1.36 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 23.29% | ±0.83% | 17.12 | 0.40 | 0.87 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
