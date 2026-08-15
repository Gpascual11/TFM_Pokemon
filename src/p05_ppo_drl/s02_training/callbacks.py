"""Win-rate logging, evolution plots, and conservative early stopping."""

from __future__ import annotations

import csv
from collections import deque
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback

from .plots import write_run_plots


class WinRateCallback(BaseCallback):
    """Log WR every ``every_steps``, redraw PNGs, optionally stop the run.

    Early stop is **not** a thesis result. Graduation is still a 1k/10k eval.
    Training WR can only halt a long job so you do not burn leftover timesteps.
    """

    def __init__(
        self,
        every_steps: int = 10_000,
        opponent_name: str = "random",
        csv_path: Path | None = None,
        plot_dir: Path | None = None,
        window: int = 200,
        title: str = "",
        target_wr: float | None = None,
        min_games: int = 300,
        patience: int = 20,
        min_delta: float = 0.01,
        enable_early_stop: bool = True,
        verbose: int = 1,
    ):
        super().__init__(verbose=verbose)
        self.every_steps = max(int(every_steps), 1)
        self.opponent_name = opponent_name
        self.csv_path = Path(csv_path) if csv_path else None
        self.plot_dir = Path(plot_dir) if plot_dir else None
        self.window = deque(maxlen=window)
        self.ep_rew = deque(maxlen=window)
        self.ep_len = deque(maxlen=window)
        self.wins = 0
        self.games = 0
        self.title = title
        self.target_wr = target_wr
        self.min_games = int(min_games)
        self.patience = int(patience)
        self.min_delta = float(min_delta)
        self.enable_early_stop = bool(enable_early_stop)
        self._last_log_step = 0
        self._best_cum = -1.0
        self._stale = 0
        self.stop_reason: str | None = None

    def _on_training_start(self) -> None:
        if self.csv_path is not None:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.csv_path.exists():
                with self.csv_path.open("w", newline="") as f:
                    csv.writer(f).writerow(
                        [
                            "step",
                            "opponent",
                            "games",
                            "wins",
                            "wr_cumulative",
                            "wr_window",
                            "window_n",
                            "ep_rew_mean",
                            "ep_len_mean",
                        ]
                    )
        if self.plot_dir is not None:
            self.plot_dir.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        infos = self.locals.get("infos") or []
        dones = self.locals.get("dones")
        if dones is None:
            dones = [info.get("battle_finished") for info in infos]
        for done, info in zip(dones, infos):
            finished = bool(done) or bool(info.get("battle_finished"))
            if not finished:
                continue
            ep = info.get("episode") or {}
            if "r" in ep:
                self.ep_rew.append(float(ep["r"]))
            if "l" in ep:
                self.ep_len.append(float(ep["l"]))
            if "battle_won" not in info:
                continue
            won = int(info.get("battle_won") or 0)
            self.games += 1
            self.wins += won
            self.window.append(won)

        if self.games <= 0:
            return True
        if self.num_timesteps - self._last_log_step < self.every_steps:
            return True
        self._last_log_step = self.num_timesteps
        wr = self.wins / self.games
        w_n = len(self.window)
        wr_w = (sum(self.window) / w_n) if w_n else 0.0
        rew = (sum(self.ep_rew) / len(self.ep_rew)) if self.ep_rew else float("nan")
        elen = (sum(self.ep_len) / len(self.ep_len)) if self.ep_len else float("nan")
        self.logger.record("winrate/cumulative", wr)
        self.logger.record("winrate/window", wr_w)
        self.logger.record("winrate/games", float(self.games))
        msg = (
            f"[step {self.num_timesteps:,}] vs {self.opponent_name}  "
            f"WR={wr:.1%} ({self.wins}/{self.games} cumulative)  "
            f"window={wr_w:.1%} n={w_n}"
        )
        print(msg, flush=True)
        if self.csv_path is not None:
            with self.csv_path.open("a", newline="") as f:
                csv.writer(f).writerow(
                    [
                        self.num_timesteps,
                        self.opponent_name,
                        self.games,
                        self.wins,
                        f"{wr:.6f}",
                        f"{wr_w:.6f}",
                        w_n,
                        f"{rew:.4f}" if self.ep_rew else "",
                        f"{elen:.2f}" if self.ep_len else "",
                    ]
                )
        self._redraw()
        return self._maybe_stop(wr, wr_w)

    def _on_training_end(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        if self.csv_path is None or self.plot_dir is None:
            return
        try:
            png = write_run_plots(
                self.csv_path,
                self.plot_dir,
                title=self.title or f"PPO vs {self.opponent_name}",
                target_wr=self.target_wr,
            )
            if png is not None and self.verbose:
                print(f"Updated plot {png}", flush=True)
        except Exception as exc:
            print(f"Plot skipped: {exc}", flush=True)

    def _maybe_stop(self, wr: float, wr_w: float) -> bool:
        if not self.enable_early_stop:
            return True
        if self.games < self.min_games:
            return True
        if self.target_wr is not None and wr_w >= self.target_wr:
            self.stop_reason = (
                f"window WR {wr_w:.1%} ≥ {self.target_wr:.0%} after {self.games} train games "
                f"(not a 1k/10k eval — still run eval to graduate)"
            )
            print(f"Early stop: {self.stop_reason}", flush=True)
            return False
        # Stall on cumulative WR. A 200-game window is ±7 pp and must not lock "best".
        if wr > self._best_cum + self.min_delta:
            self._best_cum = wr
            self._stale = 0
        else:
            self._stale += 1
        if self.patience > 0 and self._stale >= self.patience:
            self.stop_reason = (
                f"cumulative WR stalled at {wr:.1%} for {self._stale} logs "
                f"(best {self._best_cum:.1%}, patience {self.patience})"
            )
            print(f"Early stop: {self.stop_reason}", flush=True)
            return False
        return True
