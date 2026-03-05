from typing import Any

def get_agent_class(name: str) -> type:
    """Lazy-load and return the agent class for the given name."""
    
    # Internal Heuristics (v1-v6)
    if name.startswith("v"):
        try:
            version = int(name[1:])
            if 1 <= version <= 6:
                module = __import__(f"p01_heuristics.s01_singles.agents.internal.v{version}", fromlist=[f"HeuristicV{version}"])
                return getattr(module, f"HeuristicV{version}")
        except ValueError:
            pass

    # Baselines
    if name == "random":
        from poke_env.player import RandomPlayer
        return RandomPlayer
    if name == "max_power":
        from poke_env.player.baselines import MaxBasePowerPlayer
        return MaxBasePowerPlayer
    if name == "abyssal":
        from poke_env.player.baselines import AbyssalPlayer
        return AbyssalPlayer
    if name == "one_step":
        from .baselines.safe_one_step_player import SafeOneStepPlayer
        return SafeOneStepPlayer
    if name == "safe_one_step":
        from .baselines.safe_one_step_player import SafeOneStepPlayer
        return SafeOneStepPlayer
    if name == "simple_heuristic":
        from .baselines.true_simple_heuristic import TrueSimpleHeuristicsPlayer
        return TrueSimpleHeuristicsPlayer

    # LLM Agents (Pokechamp / Pokellmon)
    # These typically use a common wrapper or factory in the pokechamp repo
    if name in ["pokechamp", "pokellmon"]:
        # We handle these via the LLM factory in evaluation/engine/
        # or we could import the Pokechamp logic here if path is set
        pass

    raise ValueError(f"Unknown agent: {name}")

__all__ = ["get_agent_class"]
