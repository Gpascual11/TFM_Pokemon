# s02_training: curriculum

See [RESULTS.md](../RESULTS.md) and [RUN.md](../RUN.md). Showdown is started by the train process.

## Phases (done)

1. `train_p1_base` — RandomPlayer. Graduated 91.8% at 1k.
2. `train_p1_5_tune` — MaxBasePowerPlayer. Graduated 70.5% at 1k.
3. `train_p2_v8` — HeuristicV8. 40.6% at 1k. **BC from V8.**
4. `train_p3_v12` — HeuristicV12. Claim **34.1%** at 10k. Zip A frozen.
5. `train_p4_v14` — **BC from V14**, then PPO vs V12, 346-d obs. Snapshot ~33.5% train.

Default algorithm is MaskablePPO, `device="cuda"`, masks every step. Train WR is logged every `--wr-every` steps to `data/models/ppo/wr_logs/` and `plots/`. `wr_logs/p3_v12.csv` and `plots/p3_v12/` are **zip B**.

`train_p2_transfer` and `train_p3_gauntlet` are stubs.
