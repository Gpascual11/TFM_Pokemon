"""Plot helper: rebuild evolution PNGs from a WR CSV (no Showdown)."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.p05_ppo_drl.constants import PLOT_DIR, WR_LOG_DIR
from src.p05_ppo_drl.s02_training.plots import write_run_plots


class TestPlots(unittest.TestCase):
    def test_write_run_plots_from_csv(self):
        csv_path = WR_LOG_DIR / "p1_random.csv"
        if not csv_path.exists():
            self.skipTest("no wr csv yet")
        out = PLOT_DIR / "test_plot"
        png = write_run_plots(csv_path, out, title="test", target_wr=0.9)
        self.assertIsNotNone(png)
        self.assertTrue(Path(png).exists())
        self.assertGreater(Path(png).stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
