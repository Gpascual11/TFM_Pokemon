"""Phase 2 (optional ramp): HeuristicV8. Not poke-env SimpleHeuristics.

Loads Phase 1.5 (MaxBP) weights. Do not --resume the stalled 30% zip.
Graduate at >55% WR on 1k games vs v8.
"""

from ..constants import PHASE_CHECKPOINTS
from .loop import train_phase


def main() -> None:
    train_phase(
        phase="p2",
        opponent="v8",
        default_timesteps=1_000_000,
        default_lr=5e-5,
        default_ent_coef=0.02,
        default_port_count=8,
        load_from=PHASE_CHECKPOINTS["p15"],
        bc_games=400,
    )


if __name__ == "__main__":
    main()
