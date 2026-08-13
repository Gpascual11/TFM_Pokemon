# Executive EDA Report: Heuristic Agent `v6`

## 1. Executive Summary
- **Target Agent**: `v6`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 45.28%
- **Best Matchup**: `random` (97.37% ± 0.31%)
- **Worst Matchup**: `v12` (23.89% ± 0.84%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 57.14% | 18.89 | 0.96 | 1.04 vs 2.67 |
| **Heuristic (Basic)** | 60,000.0 | 50.18% | 17.53 | 0.41 | 1.02 vs 1.11 |
| **Heuristic (Strategic)** | 30,000.0 | 38.08% | 17.23 | -0.05 | 1.02 vs 1.46 |
| **Heuristic (Tactical)** | 20,000.0 | 36.53% | 17.25 | -0.08 | 1.02 vs 1.42 |
| **Heuristic (Tera)** | 10,000.0 | 23.89% | 17.05 | -0.46 | 1.02 vs 1.37 |
| **Heuristic (Advanced)** | 10,000.0 | 27.24% | 18.18 | -1.62 | 1.02 vs 3.21 |
| **Heuristic (Prediction)** | 10,000.0 | 33.23% | 17.68 | -1.00 | 1.02 vs 2.11 |
| **Minimax Search** | 20,000.0 | 40.28% | 18.36 | -0.67 | 1.02 vs 2.22 |
| **MCTS Search** | 11,000.0 | 36.31% | 18.13 | -0.86 | 1.01 vs 2.24 |
| **Imitation Learning** | 12,000.0 | 35.82% | 17.53 | -0.80 | 1.01 vs 2.09 |
| **Pure Imitation** | 10,000.0 | 66.57% | 19.74 | 0.80 | 1.03 vs 3.95 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.37% | ±0.31% | 25.26 | 3.56 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 80.55% | ±0.78% | 18.87 | 1.92 | 0.19 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 66.57% | ±0.92% | 19.74 | 1.42 | 0.62 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 51.53% | ±0.98% | 17.61 | 0.94 | 0.49 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 50.78% | ±0.98% | 17.31 | 0.93 | 0.49 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 50.64% | ±0.98% | 17.50 | 0.91 | 0.49 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 50.53% | ±0.98% | 17.57 | 0.91 | 0.50 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 50.10% | ±0.98% | 17.32 | 0.91 | 0.50 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 49.84% | ±0.98% | 17.57 | 0.90 | 0.51 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 49.50% | ±0.98% | 17.44 | 0.90 | 0.51 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 49.06% | ±0.98% | 17.51 | 0.88 | 0.52 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 40.35% | ±0.96% | 18.45 | 0.68 | 1.34 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 40.22% | ±0.96% | 18.27 | 0.68 | 1.36 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 39.70% | ±3.03% | 17.58 | 0.65 | 1.30 | ⚠️ N=1k (high variance) |
| `v7` | Heuristic (Strategic) | 10,000 | 39.32% | ±0.96% | 17.23 | 0.68 | 0.70 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 38.78% | ±0.95% | 17.21 | 0.65 | 0.71 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 37.91% | ±0.95% | 17.23 | 0.63 | 0.70 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 37.20% | ±3.00% | 17.88 | 0.63 | 1.31 | ⚠️ N=1k (high variance) |
| `v17` | MCTS Search | 10,000 | 36.22% | ±0.94% | 18.15 | 0.59 | 1.47 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 36.13% | ±0.94% | 17.24 | 0.66 | 0.73 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 35.55% | ±0.94% | 17.53 | 0.58 | 1.38 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 35.15% | ±0.94% | 17.27 | 0.64 | 0.72 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 34.60% | ±2.95% | 17.45 | 0.56 | 1.49 | ⚠️ N=1k (high variance) |
| `v14` | Heuristic (Prediction) | 10,000 | 33.23% | ±0.92% | 17.68 | 0.54 | 1.54 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 32.02% | ±0.91% | 17.30 | 0.57 | 0.77 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 31.99% | ±0.91% | 17.26 | 0.60 | 0.77 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 27.24% | ±0.87% | 18.18 | 0.49 | 2.11 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 23.89% | ±0.84% | 17.05 | 0.41 | 0.86 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
