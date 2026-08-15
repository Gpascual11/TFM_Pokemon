"""Phase 4: BC from V14, then PPO vs HeuristicV12. Closed — do not rerun for the claim.

Historical: loaded zip A, expanded 328→346, cloned V14 vs V12, PPO vs V12.
Aborted at ~340k, train WR 33.5%. Snapshot: p4_v14_aborted_300k.zip.
Never overwrite data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip.
Label: “BC from V14,” not V12.
"""

from ..constants import CLAIM_P3_ZIP
from .loop import train_phase


def main() -> None:
    train_phase(
        phase="p4",
        opponent="v12",
        default_timesteps=1_000_000,
        default_lr=1.5e-4,
        default_ent_coef=0.02,
        default_port_count=8,
        default_envs_per_port=2,
        load_from=CLAIM_P3_ZIP,
        bc_games=400,
        bc_expert="v14",
        bc_foe="v12",
    )


if __name__ == "__main__":
    main()
