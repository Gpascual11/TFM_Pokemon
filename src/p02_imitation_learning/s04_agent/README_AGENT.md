# Live IL agents

Gauntlet names: **`v21`** (`v21_xgboost.py`) and **`v22`** (`v22_pure_il.py`).

- **v21** — hybrid: `HeuristicV14` plus an XGBoost **stay vs switch** classifier trained on 1800+ Elo human `gen9randombattle` turns. XGB fires on a minority of turns; KO/endgame/setup still run first.
- **v22** — same macro classifier. Move ranking from a second model on candidate attributes (BP, STAB, type effectiveness).

`ml_baseline.py` is a weak stay/switch + random action agent. There is no `ml_advanced.py`; that role is v21.

Evaluate vs bots. Training humans are a different distribution.
