from typing import Any

def get_agent_class(name: str) -> type:
    """Lazy-load and return the agent class associated with a string label.

    This function maps human-readable names to their Python class implementation.
    It handles:
    1. Internal Heuristics (v1-v6) - custom rule-based agents.
    2. Baselines (random, max_power, abyssal) - standard wrappers.
    3. Optimized Baselines (simple_heuristic) - local enhancements.

    Args:
        name (str): The label of the agent (e.g. 'v6', 'abyssal').

    Returns:
        type: The Python Class for the requested player.

    Raises:
        ValueError: If the name is not recognized.
    """
    
    # Internal Heuristics (v1-v6), Search (v7), and ML (ml_baseline)
    if name.startswith("v"):
        try:
            if name == "v7_minimax":
                module = __import__(f"p02_search.s01_singles.agents.internal.v7_minimax", fromlist=["HeuristicV7Minimax"])
                return getattr(module, "HeuristicV7Minimax")
            version = int(name[1:])
            if 1 <= version <= 6:
                module = __import__(f"p01_heuristics.s01_singles.agents.internal.v{version}", fromlist=[f"HeuristicV{version}"])
                return getattr(module, f"HeuristicV{version}")
        except ValueError:
            pass
            
    if name == "ml_baseline":
        module = __import__(f"p03_ml_baseline.s04_agent.ml_baseline", fromlist=["MLBaselineAgent"])
        return getattr(module, "MLBaselineAgent")

    # Baselines
    if name == "random":
        from poke_env.player import RandomPlayer
        return RandomPlayer
    if name == "max_power":
        from poke_env.player.baselines import MaxBasePowerPlayer
        return MaxBasePowerPlayer
    if name == "abyssal":
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent.parent.parent.resolve()
        pokechamp_path = root / "pokechamp"
        if pokechamp_path.exists() and str(pokechamp_path) not in sys.path:
            sys.path.insert(0, str(pokechamp_path))
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
