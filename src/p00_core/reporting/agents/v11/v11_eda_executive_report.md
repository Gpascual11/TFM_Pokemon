# Executive EDA Report: Heuristic Agent `v11`

## 1. Executive Summary
- **Target Agent**: `v11`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 59.26%
- **Best Matchup**: `random` (98.53% ± 0.24%)
- **Worst Matchup**: `v12` (37.79% ± 0.95%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 68.49% | 18.10 | 1.65 | 1.42 vs 2.52 |
| **Heuristic (Basic)** | 60,000.0 | 65.00% | 17.25 | 1.14 | 1.32 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 53.44% | 17.51 | 0.62 | 1.41 vs 1.57 |
| **Heuristic (Tactical)** | 20,000.0 | 52.20% | 17.44 | 0.62 | 1.40 vs 1.51 |
| **Heuristic (Tera)** | 10,000.0 | 37.79% | 17.59 | 0.11 | 1.45 vs 1.49 |
| **Heuristic (Advanced)** | 10,000.0 | 42.53% | 18.78 | -0.61 | 1.58 vs 3.71 |
| **Heuristic (Prediction)** | 10,000.0 | 46.42% | 18.23 | -0.28 | 1.47 vs 2.29 |
| **Minimax Search** | 20,000.0 | 56.64% | 18.62 | 0.25 | 1.41 vs 2.18 |
| **MCTS Search** | 11,000.0 | 51.55% | 18.45 | -0.00 | 1.42 vs 2.25 |
| **Imitation Learning** | 12,000.0 | 50.67% | 17.96 | -0.05 | 1.44 vs 2.14 |
| **Pure Imitation** | 10,000.0 | 76.18% | 19.06 | 1.61 | 1.43 vs 3.81 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 98.53% | ±0.24% | 21.88 | 4.14 | 0.02 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 87.60% | ±0.65% | 17.52 | 2.59 | 0.12 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 76.18% | ±0.83% | 19.06 | 2.06 | 0.46 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 65.71% | ±0.93% | 17.18 | 1.52 | 0.35 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 65.66% | ±0.93% | 17.03 | 1.51 | 0.34 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 65.22% | ±0.93% | 17.23 | 1.49 | 0.34 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 65.16% | ±0.93% | 17.29 | 1.48 | 0.35 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 64.82% | ±0.94% | 17.19 | 1.49 | 0.35 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 64.62% | ±0.94% | 17.24 | 1.48 | 0.35 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 64.44% | ±0.94% | 17.35 | 1.46 | 0.36 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 64.35% | ±0.94% | 17.09 | 1.48 | 0.35 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 57.24% | ±0.97% | 18.55 | 1.26 | 0.97 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 56.20% | ±3.08% | 18.11 | 1.25 | 0.94 | ⚠️ N=1k (high variance) |
| `v19` | Imitation Learning | 1,000 | 56.20% | ±3.08% | 18.20 | 1.24 | 0.97 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 56.04% | ±0.97% | 18.70 | 1.19 | 0.99 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 55.51% | ±0.97% | 17.49 | 1.18 | 0.52 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 54.32% | ±0.98% | 17.48 | 1.14 | 0.54 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 54.20% | ±0.98% | 17.40 | 1.16 | 0.53 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 51.09% | ±0.98% | 18.49 | 1.08 | 1.11 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 50.60% | ±3.10% | 18.19 | 1.03 | 1.14 | ⚠️ N=1k (high variance) |
| `v9` | Heuristic (Strategic) | 10,000 | 50.48% | ±0.98% | 17.54 | 1.16 | 0.58 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 50.19% | ±0.98% | 17.48 | 1.16 | 0.57 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 50.12% | ±0.98% | 17.91 | 1.01 | 1.09 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 47.50% | ±0.98% | 17.49 | 1.11 | 0.60 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 47.32% | ±0.98% | 17.61 | 1.13 | 0.60 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 46.42% | ±0.98% | 18.23 | 0.94 | 1.22 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 42.53% | ±0.97% | 18.78 | 1.05 | 1.65 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 37.79% | ±0.95% | 17.59 | 0.82 | 0.71 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
