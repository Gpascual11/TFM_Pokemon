"""Run unit tests (masks, vectorizer, CUDA). Showdown smoke is a separate command."""

from __future__ import annotations

import unittest


def main() -> None:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromName("src.p05_ppo_drl.tests.test_action_masks"))
    suite.addTests(loader.loadTestsFromName("src.p05_ppo_drl.tests.test_vectorizer"))
    suite.addTests(loader.loadTestsFromName("src.p05_ppo_drl.tests.test_cuda_forward"))
    suite.addTests(loader.loadTestsFromName("src.p05_ppo_drl.tests.test_plots"))
    suite.addTests(loader.loadTestsFromName("src.p05_ppo_drl.tests.test_opponents"))
    suite.addTests(loader.loadTestsFromName("src.p05_ppo_drl.tests.test_early_stop"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
