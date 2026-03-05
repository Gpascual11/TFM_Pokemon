"""Factory for instantiating heuristic players by version string.

Usage::

    player = HeuristicFactory.create("v5", battle_format="gen9randombattle", ...)
"""

from __future__ import annotations

from typing import Any

from ..agents import get_heuristic_class
from .base import BaseHeuristic1v1


class HeuristicFactory:
    """Creates :class:`BaseHeuristic1v1` subclasses by version label."""

    @staticmethod
    def available_versions() -> list[str]:
        """Return sorted list of registered version labels."""
        return ["v1", "v2", "v3", "v4", "v5", "v6"]

    @staticmethod
    def create(version: str, **player_kwargs: Any) -> BaseHeuristic1v1:
        """Instantiate the heuristic identified by *version*.

        :param version: Registered label, e.g. ``v1`` or ``v5``.
        :raises ValueError: If *version* is not registered.
        """
        cls = get_heuristic_class(version)
        return cls(**player_kwargs)
