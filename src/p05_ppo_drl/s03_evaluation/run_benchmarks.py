"""Removed: claim eval is eval_checkpoint vs v12, not a SimpleHeuristics gauntlet."""

raise SystemExit(
    "Do not run this gauntlet. Claim eval:\n"
    "  uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \\\n"
    "    --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent v12 "
    "--games 10000 --both-seats --ports 8\n"
    "See src/p05_ppo_drl/RESULTS.md. Prefer not to re-run; the 10k JSON is on disk."
)
