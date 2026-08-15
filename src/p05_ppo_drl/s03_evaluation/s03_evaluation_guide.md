# s03_evaluation: Random sanity + v12 claim

Claim opponent is HeuristicV12. **34.1%** at n=10k is on disk.

```bash
uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent v12 --games 10000 --both-seats --ports 8
```

JSON: `data/models/ppo/eval/pure_ppo_vs_v12_n10000.json`. Re-running overwrites those filenames.

| n | Meaning |
|---|---|
| 100 | smoke ±10 pp |
| 1k | diagnostic ±3.1 pp |
| 10k | claim ±0.93 pp |
