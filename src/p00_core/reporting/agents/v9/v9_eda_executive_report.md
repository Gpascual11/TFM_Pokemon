# Executive EDA Report: Heuristic Agent `v9`

## 1. Executive Summary
- **Target Agent**: `v9`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 58.86%
- **Best Matchup**: `random` (98.43% ± 0.24%)
- **Worst Matchup**: `v12` (37.69% ± 0.95%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 68.50% | 18.16 | 1.65 | 1.48 vs 2.53 |
| **Heuristic (Basic)** | 60,000.0 | 64.49% | 17.27 | 1.12 | 1.37 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 53.00% | 17.51 | 0.62 | 1.46 vs 1.58 |
| **Heuristic (Tactical)** | 20,000.0 | 51.59% | 17.48 | 0.59 | 1.45 vs 1.52 |
| **Heuristic (Tera)** | 10,000.0 | 37.69% | 17.63 | 0.12 | 1.52 vs 1.49 |
| **Heuristic (Advanced)** | 10,000.0 | 41.87% | 18.74 | -0.64 | 1.62 vs 3.74 |
| **Heuristic (Prediction)** | 10,000.0 | 45.74% | 18.22 | -0.28 | 1.53 vs 2.28 |
| **Minimax Search** | 20,000.0 | 55.69% | 18.65 | 0.23 | 1.51 vs 2.16 |
| **MCTS Search** | 11,000.0 | 51.35% | 18.49 | -0.03 | 1.53 vs 2.24 |
| **Imitation Learning** | 12,000.0 | 50.20% | 17.96 | -0.05 | 1.51 vs 2.16 |
| **Pure Imitation** | 10,000.0 | 75.65% | 19.14 | 1.60 | 1.46 vs 3.83 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 98.43% | ±0.24% | 21.98 | 4.16 | 0.02 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 87.94% | ±0.64% | 17.62 | 2.60 | 0.12 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 75.65% | ±0.84% | 19.14 | 2.06 | 0.46 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 65.49% | ±0.93% | 17.12 | 1.50 | 0.34 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 65.48% | ±0.93% | 17.04 | 1.50 | 0.34 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 65.11% | ±0.93% | 17.30 | 1.51 | 0.34 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 64.70% | ±0.94% | 17.20 | 1.50 | 0.36 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 64.69% | ±0.94% | 17.30 | 1.50 | 0.35 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 64.49% | ±0.94% | 17.21 | 1.47 | 0.36 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 64.27% | ±0.94% | 17.28 | 1.47 | 0.36 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 63.69% | ±0.94% | 17.32 | 1.44 | 0.36 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 56.40% | ±3.07% | 18.15 | 1.28 | 0.94 | ⚠️ N=1k (high variance) |
| `v19` | Imitation Learning | 1,000 | 56.00% | ±3.08% | 18.64 | 1.30 | 0.90 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 55.99% | ±0.97% | 18.78 | 1.23 | 0.98 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 55.39% | ±0.97% | 18.52 | 1.22 | 1.00 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 55.11% | ±0.97% | 17.54 | 1.20 | 0.52 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 53.79% | ±0.98% | 17.48 | 1.15 | 0.53 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 53.58% | ±0.98% | 17.47 | 1.14 | 0.54 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 50.84% | ±0.98% | 18.52 | 1.06 | 1.12 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 50.32% | ±0.98% | 17.51 | 1.18 | 0.59 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 49.95% | ±0.98% | 17.87 | 1.01 | 1.09 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 49.40% | ±0.98% | 17.48 | 1.14 | 0.58 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 47.01% | ±0.98% | 17.66 | 1.11 | 0.61 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 46.90% | ±3.09% | 18.12 | 0.98 | 1.18 | ⚠️ N=1k (high variance) |
| `abyssal` | Baseline | 10,000 | 46.64% | ±0.98% | 17.56 | 1.10 | 0.62 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 45.74% | ±0.98% | 18.22 | 0.94 | 1.23 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 41.87% | ±0.97% | 18.74 | 1.03 | 1.67 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 37.69% | ±0.95% | 17.63 | 0.83 | 0.72 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
