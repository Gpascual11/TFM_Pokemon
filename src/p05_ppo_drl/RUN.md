# PPO vs HeuristicV12 — reproduce the claim

Keep `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip`.

Python 3.12, `uv run python -m …` from the repo root. GPU (`device="cuda"`). Showdown starts inside the process.

**Claim:** **BC from V8 + PPO** vs HeuristicV12, n=10k, both seats: **34.1%** (3405/10000) ± 0.93 pp. Details: [RESULTS.md](RESULTS.md).

Frozen claim spaces: **obs_size=328**, **action_n=14**. Current code vectorizer is 346-d (Phase 4 append); loading zip A expands the first layer and zero-inits the extra 18 dims.

Sample sizes: **100 = smoke.** **1k = diagnostic.** **10k = the PPO vs v12 number.**

---

## Unit tests

```bash
uv run python -m src.p05_ppo_drl.tests.run_unit
```

---

## Reproduce the claim eval

Zip A: `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip`.

```bash
uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent random --games 1000

uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent v12 --games 10000 --both-seats --ports 8
```

On disk: `data/models/ppo/eval/pure_ppo_vs_v12_n10000.json` (**34.1%**), sanity `pure_ppo_vs_random_n1000.json` (**98.3%**, zip A vs Random). `pure_ppo_vs_v12_n1000.json` is **zip B 32.6%**. Re-running eval overwrites those filenames.

How to read n=10k vs v12: **≥51% = edge; 50±1 = coin flip; ~45% = knowledge-ceiling loss.** 34.1% is a measured loss in the V8-vs-V12 band (gauntlet 32.9%).

---

## Optional `--hybrid` ablation

Mixes PPO with HeuristicV12 at **test time**. Label hybrid.

```bash
uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent v12 --games 1000 --hybrid --alpha 0.5
```

---

## Phase 4 snapshot

`data/models/ppo/p4_v14/p4_v14_aborted_300k.zip` — **BC from V14** + 346-d obs, ~340k, train WR 33.5%. Same ~33% floor.

---

## Historical train commands

Curriculum entrypoints still exist (`train_p1_base`, `train_p1_5_tune`, `train_p2_v8`, `train_p3_v12`, `train_p4_v14`). Phase 3 `--resume` would look for the old `p3_v12.zip` (renamed to `p3_v12_stale_160k_interrupt.zip`). Lab notebook: [p2_v8_notes.md](p2_v8_notes.md).

On exit only Showdown processes **that run started** are stopped. A hard abort can leave ports 8000–8007 up; the next train does `restart=True`.
