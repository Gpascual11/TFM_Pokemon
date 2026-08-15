"""Frozen PPO experiment constants.

Changing ``ACTION_N`` invalidates every zip. Claim zips are 328-d; Phase 4 is 346-d
(first layer expanded on load). Do not overwrite ``CLAIM_P3_ZIP``.
"""

from __future__ import annotations

from pathlib import Path

from ._bootstrap import repo_root

BATTLE_FORMAT = "gen9randombattle"
DEVICE = "cuda"

N_MOVES = 4
N_SWITCHES = 6
# 4 moves + 4 moves+Tera + 6 switches
ACTION_N = N_MOVES + N_MOVES + N_SWITCHES  # 14
MOVE_OFFSET = 0
TERA_OFFSET = N_MOVES  # 4
SWITCH_OFFSET = N_MOVES + N_MOVES  # 8

DEFAULT_N_SERVERS = 4
BASE_PORT = 8000
DEFAULT_PORTS = list(range(BASE_PORT, BASE_PORT + DEFAULT_N_SERVERS))

ROOT = repo_root()
CHECKPOINT_DIR = ROOT / "data" / "models" / "ppo"
TB_DIR = CHECKPOINT_DIR / "tb"
WR_LOG_DIR = CHECKPOINT_DIR / "wr_logs"
PLOT_DIR = CHECKPOINT_DIR / "plots"
EVAL_DIR = CHECKPOINT_DIR / "eval"

# One folder per curriculum phase: final zip at <dir>/<stem>.zip, intermediates in ckpts/.
PHASE_NAMES = {
    "p1": "p1_random",
    "p15": "p15_maxbp",
    "p2": "p2_v8",
    "p3": "p3_v12",
    "p4": "p4_v14",
}
PHASE_DIRS = {k: CHECKPOINT_DIR / v for k, v in PHASE_NAMES.items()}
PHASE_CHECKPOINTS = {k: d / f"{PHASE_NAMES[k]}.zip" for k, d in PHASE_DIRS.items()}
# Publishable Phase 3 zip. Do not --resume, delete, or save over this file.
CLAIM_P3_ZIP = PHASE_DIRS["p3"] / "p3_v12_lr5e5_flat.zip"

NET_ARCH = [256, 256]

# Conservative train-loop early stop. Graduation is still a 1k/10k eval.
# Phase 3 has no WR target: a train-window ≥51% vs v12 is not a claim.
PHASE_EARLY_STOP = {
    "p1": {"target_wr": 0.90, "min_games": 300, "patience": 20},
    "p15": {"target_wr": 0.70, "min_games": 300, "patience": 20},
    "p2": {"target_wr": 0.55, "min_games": 800, "patience": 40},
    "p3": {"target_wr": None, "min_games": 500, "patience": 30},
    "p4": {"target_wr": None, "min_games": 500, "patience": 40},
}


def ensure_model_dirs() -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    TB_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    WR_LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    Path(CHECKPOINT_DIR / ".gitkeep").touch(exist_ok=True)
    for d in PHASE_DIRS.values():
        ckpts = d / "ckpts"
        d.mkdir(parents=True, exist_ok=True)
        ckpts.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch(exist_ok=True)
        (ckpts / ".gitkeep").touch(exist_ok=True)
