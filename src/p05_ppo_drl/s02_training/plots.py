"""Evolution plots for a PPO run. Written under ``data/models/ppo/plots/``."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def write_run_plots(
    csv_path: Path,
    out_dir: Path,
    *,
    title: str,
    target_wr: float | None = None,
) -> Path | None:
    """Redraw win-rate (and reward/length if present) from the WR CSV.

    Returns the main PNG path, or None if there is nothing to plot.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None
    if df.empty or "step" not in df.columns:
        return None

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    has_reward = "ep_rew_mean" in df.columns and df["ep_rew_mean"].notna().any()
    n_rows = 2 if has_reward else 1
    fig, axes = plt.subplots(n_rows, 1, figsize=(10, 4.2 * n_rows), sharex=True)
    if n_rows == 1:
        axes = [axes]
    ax = axes[0]
    ax.plot(df["step"], df["wr_cumulative"] * 100, label="cumulative WR", color="#2563eb")
    ax.plot(df["step"], df["wr_window"] * 100, label="rolling window WR", color="#f59e0b")
    ax.axhline(50, color="#ef4444", ls="--", lw=1, alpha=0.8, label="coin flip 50%")
    if target_wr is not None:
        ax.axhline(
            target_wr * 100,
            color="#16a34a",
            ls=":",
            lw=1.4,
            label=f"train early-stop {target_wr:.0%}",
        )
    ax.set_ylabel("Win rate %")
    ax.set_title(title)
    ax.set_ylim(0, 100)
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    last = df.iloc[-1]
    ax.text(
        0.99,
        0.04,
        f"step {int(last['step']):,}  games {int(last['games'])}  "
        f"WR {float(last['wr_cumulative'])*100:.1f}%",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#334155",
    )

    if has_reward:
        ax2 = axes[1]
        ax2.plot(df["step"], df["ep_rew_mean"], color="#7c3aed", label="mean episode reward")
        ax2.set_ylabel("Episode reward")
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="upper left", fontsize=8)
        if "ep_len_mean" in df.columns and df["ep_len_mean"].notna().any():
            ax3 = ax2.twinx()
            ax3.plot(df["step"], df["ep_len_mean"], color="#0ea5e9", ls="--", label="mean episode length")
            ax3.set_ylabel("Episode length (steps)")
            ax3.legend(loc="upper right", fontsize=8)
        ax2.set_xlabel("Timesteps")
    else:
        ax.set_xlabel("Timesteps")

    fig.tight_layout()
    png = out_dir / "winrate.png"
    fig.savefig(png, dpi=140)
    fig.savefig(out_dir / "latest.png", dpi=140)
    plt.close(fig)
    return png
