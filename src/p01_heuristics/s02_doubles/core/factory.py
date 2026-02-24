"""Factory for instantiating 2v2 heuristic players by version string."""

from __future__ import annotations

from typing import Any

from ..agents import HEURISTIC_REGISTRY


class HeuristicFactory:
    """Creates :class:`BaseHeuristic2v2` subclasses by version label."""

    @staticmethod
    def available_versions() -> list[str]:
        """Return sorted registered version labels."""
        return sorted(HEURISTIC_REGISTRY.keys())

    @staticmethod
    def create(version: str, **player_kwargs: Any):
        """Instantiate the heuristic identified by *version*.

        :raises ValueError: If *version* is not registered.
        """
        cls = HEURISTIC_REGISTRY.get(version)
        if cls is None:
            valid = ", ".join(HeuristicFactory.available_versions())
            raise ValueError(f"Unknown version '{version}'. Available: {valid}")
        return cls(**player_kwargs)
