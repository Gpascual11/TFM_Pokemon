#!/usr/bin/env python
"""Backwards-compatible shim.

This file used to live in `evaluation/engine/`. It now lives in
`evaluation/debug/debug_runner.py`.
"""

from __future__ import annotations

from p01_heuristics.s01_singles.evaluation.debug.debug_runner import main


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

