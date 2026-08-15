# Results — MaskablePPO vs HeuristicV12

Claim opponent is **HeuristicV12**. Format `gen9randombattle`. Default eval agent is neural PPO (`PPOPlayer`).

How to read n=10k vs V12: **≥51% = edge; 50±1 = coin flip; ~45% = knowledge-ceiling loss.** This run matches **V8 vs V12 in the 10k gauntlet (32.9%)**.

## Claim (the table number)

**BC from V8 + PPO** vs HeuristicV12, n=10k, both seats, 8 ports:

**34.1%** (3405/10000) ± 0.93 pp (CI ~33.2–35.0%). p1 34.2% (1709/5000), p2 33.9% (1696/5000). Mean turns 17.2. 450s.

- Zip: `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip` (328-d, 8 envs, lr 5e-5, **zip A**)
- JSON: `data/models/ppo/eval/pure_ppo_vs_v12_n10000.json`
- Sanity n=1k vs Random on zip A: **98.3%** (983/1000) ± 0.80 pp
- Diagnostic n=1k vs V12 on zip A: **36.0%** (360/1000) ± 2.98 pp (JSON later overwritten — see below)

Label: **BC from V8 + PPO**.

## Curriculum

| Phase | Opponent | Zip | Eval | Graduate? |
|---|---|---|---|---|
| 1 | Random | `p1_random/p1_random.zip` (318-d) | n=1k **91.8%** (918/1000) ± 1.70 pp | Yes (≥90%) |
| 1.5 | MaxBP | `p15_maxbp/p15_maxbp.zip` (318-d) | n=1k **70.5%** (705/1000) ± 2.83 pp | Yes (point estimate >70%) |
| 2 | V8 | `p2_v8/p2_v8.zip` (328-d) | n=1k **40.6%** (406/1000) ± 3.04 pp | Ramp (threshold was >55%) |
| 3 | V12 | **zip A** `p3_v12_lr5e5_flat.zip` (328-d) | n=10k **34.1%** | Claim |
| 3B | V12 | `p3_v12_lr15e4_400k.zip` (328-d) | n=1k **32.6%** | Secondary run |
| 4 | V12 | `p4_v14_aborted_300k.zip` (346-d) | train **33.5%** at 340k | Snapshot; same floor |

Gauntlet context (`heur_winrate_by_opponent.csv`, row `v12`): V1 23.3%, V8 32.9%, V12 50.1%, **V14 44.7%**.

Phase 1’s 91.8% JSON is gone (`pure_ppo_vs_random_n1000.json` is zip A’s 98.3% sanity). Zip A’s 36.0% vs V12 at 1k is gone (`pure_ppo_vs_v12_n1000.json` is zip B’s 32.6%). Both numbers are recorded here and in the lab notes.

## Additional curriculum runs

1. **Hotter PPO vs V12** (zip B, lr 1.5e-4, 16 envs). n=1k **32.6%**.
2. **Richer obs (346-d) + BC from V14**, then PPO vs V12. In-battle clone: agree 79.7%. First 10k train WR **34.1%**. Snapshot at ~340k, train WR **33.5%** (4203/12554). Label: **BC from V14**.
3. Observation covers in-battle state (matchup, Tera, hazards). V14 vs V12 (44.7%) is in-battle knowledge. Claim remains zip A.

## Frozen spaces

- Claim zips: **obs 328**, action **Discrete(14)** (4 moves + 4 Tera + 6 switches).
- Phase 4 code path is **obs 346** (18 dims appended: revealed-team matchup, best-matchup flag, tera damage/def, switch-in hazard). Claim 328 zips load by expanding the first layer. Published 34.1% is the 328-d net.

## Files for the thesis

| Path | Use |
|---|---|
| `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip` | Claim weights |
| `data/models/ppo/eval/pure_ppo_vs_v12_n10000.json` | Claim JSON |
| `data/models/ppo/eval/pure_ppo_vs_v8_n1000.json` | Phase 2 diagnostic |
| `data/models/ppo/eval/pure_ppo_vs_maxbp_n1000.json` | Phase 1.5 diagnostic |
| `data/models/ppo/eval/pure_ppo_vs_random_n1000.json` | Zip A sanity (98.3%) |
| `data/models/ppo/plots/p3_v12/winrate.png` | **Zip B** train curve |
| `data/models/ppo/plots/p4_v12/winrate.png` | Phase 4 train curve |
| [p2_v8_notes.md](p2_v8_notes.md) | Lab notebook |
| `data/models/ppo/README.md` | Zip index |

## Reproduce

Keep **34.1% ± 0.93 pp** in the thesis table (BC from V8 + PPO vs V12, n=10k). Eval commands: [RUN.md](RUN.md). Optional footnote: `--hybrid` n=1k, labeled hybrid.
