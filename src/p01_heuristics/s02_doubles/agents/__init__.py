"""Unified Registry for Doubles Agents."""

from __future__ import annotations

def get_agent_class(name: str) -> type:
    """Lazy-load and return the agent class for the given name."""
    
    # Internal Heuristics
    if name == "v1":
        from .internal.v1 import HeuristicV1Doubles
        return HeuristicV1Doubles
    if name == "v2":
        from .internal.v2 import HeuristicV2Doubles
        return HeuristicV2Doubles
    if name == "v6":
        from .internal.v6 import HeuristicV6Doubles
        return HeuristicV6Doubles
        
    # Baselines
    if name == "random":
        from poke_env.player import RandomPlayer
        return RandomPlayer
    if name == "max_power":
        from poke_env.player.baselines import MaxBasePowerPlayer
        return MaxBasePowerPlayer
    if name == "abyssal":
        from .baselines.abyssal_doubles import AbyssalPlayer
        return AbyssalPlayer
    if name == "one_step":
        from .baselines.safe_one_step_doubles import SafeOneStepDoublesPlayer
        return SafeOneStepDoublesPlayer
    if name == "safe_one_step":
        from .baselines.safe_one_step_doubles import SafeOneStepDoublesPlayer
        return SafeOneStepDoublesPlayer
    if name == "vgc":
        from .baselines.vgc_doubles import VGCDoublesPlayer
        return VGCDoublesPlayer
    if name == "simple_heuristic":
        from poke_env.player.baselines import SimpleHeuristicsPlayer
        return SimpleHeuristicsPlayer

    raise ValueError(f"Unknown doubles agent: {name}")

__all__ = ["get_agent_class"]
