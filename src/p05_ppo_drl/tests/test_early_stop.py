"""Early-stop must not treat a noisy 200-game window spike as a plateau."""

from __future__ import annotations

import unittest

from src.p05_ppo_drl.s02_training.callbacks import WinRateCallback


class TestEarlyStop(unittest.TestCase):
    def _cb(self) -> WinRateCallback:
        cb = WinRateCallback(target_wr=0.55, min_games=0, patience=3, min_delta=0.01, enable_early_stop=True)
        cb.games = 500
        return cb

    def test_noisy_window_does_not_stall_if_cumulative_rises(self):
        cb = self._cb()
        self.assertTrue(cb._maybe_stop(0.30, 0.38))
        self.assertTrue(cb._maybe_stop(0.301, 0.28))
        self.assertTrue(cb._maybe_stop(0.302, 0.29))
        self.assertTrue(cb._maybe_stop(0.312, 0.28))
        self.assertIsNone(cb.stop_reason)

    def test_true_cumulative_stall_stops(self):
        cb = self._cb()
        self.assertTrue(cb._maybe_stop(0.30, 0.30))
        self.assertTrue(cb._maybe_stop(0.300, 0.31))
        self.assertTrue(cb._maybe_stop(0.301, 0.29))
        self.assertFalse(cb._maybe_stop(0.301, 0.28))
        self.assertIsNotNone(cb.stop_reason)
        self.assertIn("cumulative", cb.stop_reason)

    def test_window_target_still_stops(self):
        cb = self._cb()
        self.assertFalse(cb._maybe_stop(0.40, 0.56))
        self.assertIn("window WR", cb.stop_reason)


if __name__ == "__main__":
    unittest.main()
