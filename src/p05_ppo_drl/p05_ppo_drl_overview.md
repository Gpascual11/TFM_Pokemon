# p05_ppo_drl: MaskablePPO vs HeuristicV12

Finished. Separate experiment from the 28-agent / 784-file gauntlet. Claim opponent is HeuristicV12 (`get_agent_class("v12")`) on `gen9randombattle`.

**Claim (n=10k, both seats, zip A):** **BC from V8 + PPO** vs HeuristicV12 **34.1%** (3405/10000) ± 0.93 pp. Same band as V8 vs V12 in the gauntlet (32.9%). Numbers: [RESULTS.md](RESULTS.md). Lab: [p2_v8_notes.md](p2_v8_notes.md).

## Frozen spaces

- Claim observation: **328** floats in [0, 1]. Phase 4 code is **346** (18 dims appended: revealed-team matchup, best-matchup flag, tera move/def, switch-in hazard). Claim 328 zips load by expanding the first Linear layer. Phase 1/1.5 zips were 318.
- Actions: **Discrete(14)** — 4 moves, 4 moves+Tera (`battle.can_tera` + `SingleBattleOrder(..., terastallize=True)`), 6 switches. `action_masks` and `action_to_order` share `s01_env/actions.py`.

## Pipeline

| Phase | Script | Opponent | Outcome |
|---|---|---|---|
| 1 | `train_p1_base` | RandomPlayer | Graduated 91.8% at 1k |
| 1.5 | `train_p1_5_tune` | MaxBasePowerPlayer | Graduated 70.5% at 1k |
| 2 | `train_p2_v8` | HeuristicV8 | Ramp 40.6% at 1k. **BC from V8.** |
| 3 | `train_p3_v12` | HeuristicV12 | **Claim 34.1% at 10k.** Zip A frozen |
| 4 | `train_p4_v14` | V12, **BC from V14** | Snapshot ~33.5% train |

Eval: vs Random (sanity) + vs v12. Dev 1k, final 10k. Default agent is **pure PPO**. `--hybrid` is an ablation labeled hybrid (PPO+v12).

Phase 4, if mentioned, is **BC from V14** + 346-d obs, same floor. `train_p2_transfer` and `train_p3_gauntlet` are stubs.

## Layout

- `s01_env/` — env, masks, vectorizer
- `s02_training/` — Showdown helper + curriculum. Servers start inside the train script
- `s03_evaluation/` — `eval_checkpoint` vs random / v12
- `tests/` — masks, CUDA forward
- **[README.md](README.md)** — index
- **[RESULTS.md](RESULTS.md)** — thesis numbers
- **[RUN.md](RUN.md)** — reproduce the claim eval
- **[p2_v8_notes.md](p2_v8_notes.md)** — curriculum notes

Checkpoints: `data/models/ppo/` (see that folder’s README)  
TensorBoard leftovers: `data/models/ppo/tb/`
