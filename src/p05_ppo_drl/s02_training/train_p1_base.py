"""Phase 1: MaskablePPO vs poke-env RandomPlayer. Graduate at ≥90% WR, n=1k games."""

from .loop import train_phase


def main() -> None:
    train_phase(
        phase="p1",
        opponent="random",
        default_timesteps=500_000,
        default_lr=3e-4,
        load_from=None,
    )


if __name__ == "__main__":
    main()
