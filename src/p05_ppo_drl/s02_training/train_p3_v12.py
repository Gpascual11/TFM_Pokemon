"""Phase 3: train vs HeuristicV12. Closed — claim zip is p3_v12_lr5e5_flat.zip (34.1% n=10k).

Do not --resume. Do not save over the claim file. PHASE_CHECKPOINTS['p3'] is the old stem name.
"""

from ..constants import PHASE_CHECKPOINTS
from .loop import train_phase


def main() -> None:
    train_phase(
        phase="p3",
        opponent="v12",
        default_timesteps=1_000_000,
        default_lr=5e-5,
        load_from=PHASE_CHECKPOINTS["p2"],
    )


if __name__ == "__main__":
    main()
