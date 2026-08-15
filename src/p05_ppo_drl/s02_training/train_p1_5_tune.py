"""Phase 1.5: resume Phase 1 vs MaxBasePowerPlayer. Graduate at >70% WR, n=1k."""

from ..constants import PHASE_CHECKPOINTS
from .loop import train_phase


def main() -> None:
    train_phase(
        phase="p15",
        opponent="maxbp",
        default_timesteps=500_000,
        default_lr=2e-4,
        load_from=PHASE_CHECKPOINTS["p1"],
    )


if __name__ == "__main__":
    main()
