"""Curriculum opponents must import on the installed poke-env (no Showdown)."""

from __future__ import annotations

import unittest

from src.p05_ppo_drl._bootstrap import ensure_src_path

ensure_src_path()


class TestOpponentImports(unittest.TestCase):
    def test_v8_class_loads(self):
        from p01_heuristics.agents import get_agent_class

        cls = get_agent_class("v8")
        self.assertEqual(cls.__name__, "HeuristicV8")

    def test_v14_class_loads(self):
        from p01_heuristics.agents import get_agent_class

        cls = get_agent_class("v14")
        self.assertEqual(cls.__name__, "HeuristicV14")


if __name__ == "__main__":
    unittest.main()
