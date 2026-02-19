"""Factory for instantiating heuristic players by version string.

Usage::

    player = HeuristicFactory.create("v5", battle_format="gen9randombattle", ...)
"""

from __future__ import annotations

from typing import Any

from .base import BaseHeuristic1v1
from .heuristics import HEURISTIC_REGISTRY


class HeuristicFactory:
    """Create a :class:`BaseHeuristic1v1` subclass by version label."""

    @staticmethod
    def available_versions() -> list[str]:
        """Return sorted list of registered version labels."""
        return sorted(HEURISTIC_REGISTRY.keys())

    @staticmethod
    def create(version: str, **player_kwargs: Any) -> BaseHeuristic1v1:
        """Instantiate the heuristic identified by *version*.

        Parameters
        ----------
        version : str
            One of the registered labels (e.g. ``v1``, ``v5``).
        **player_kwargs
            Forwarded to the ``Player`` constructor
            (``battle_format``, ``account_configuration``, etc.).

        Raises
        ------
        ValueError
            If *version* is not registered.
        """
        cls = HEURISTIC_REGISTRY.get(version)
        if cls is None:
            valid = ", ".join(HeuristicFactory.available_versions())
            raise ValueError(
                f"Unknown heuristic version '{version}'. Available: {valid}"
            )
        return cls(**player_kwargs)
