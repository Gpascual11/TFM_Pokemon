# p05_ppo_drl — MaskablePPO vs HeuristicV12

Experiment finished. Claim zip: `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip`.

| | |
|---|---|
| Claim opponent | HeuristicV12 (`get_agent_class("v12")`), `gen9randombattle` |
| Claim number | **34.1%** (3405/10000) ± 0.93 pp, both seats, n=10k |
| Zip | `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip` |
| Label | **BC from V8 + PPO** |
| Scope | Separate from the 28-agent / 784-file gauntlet |

n=100 is smoke. n=1k is diagnostic. n=10k is the PPO vs V12 number.

## Read these

| File | What it is |
|---|---|
| [RESULTS.md](RESULTS.md) | Thesis table: curriculum, claim, extra runs |
| [RUN.md](RUN.md) | Commands to **reproduce** eval |
| [p2_v8_notes.md](p2_v8_notes.md) | Lab notebook (BC, curriculum, Phase 3/4) |
| [p05_ppo_drl_overview.md](p05_ppo_drl_overview.md) | Spaces, pipeline, layout |
| [s01_env/s01_env_guide.md](s01_env/s01_env_guide.md) | Discrete(14) + observation |
| [s02_training/s02_training_guide.md](s02_training/s02_training_guide.md) | Train loop |
| [s03_evaluation/s03_evaluation_guide.md](s03_evaluation/s03_evaluation_guide.md) | Eval sample sizes |
| `data/models/ppo/README.md` | Zip index |

## Artifacts to keep

- Claim zip `p3_v12_lr5e5_flat.zip` (zip A)
- Phase 4 labeled **BC from V14** (same ~33% floor)
- Default eval agent is pure PPO; `--hybrid` mixes PPO with V12 at test time
- `eval/pure_ppo_vs_v12_n1000.json` is zip B; `plots/p3_v12/` is zip B’s curve
