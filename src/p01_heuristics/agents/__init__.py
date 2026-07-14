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
    
    # Internal Heuristics (v1-v8), Search (v7_minimax), and ML (ml_baseline)
    if name.startswith("v"):
        try:
            if name in ["v15", "v15_minimax"]:
                module = __import__("p03_minmax.agents.internal.v15_minimax", fromlist=["HeuristicV15Minimax"])
                return module.HeuristicV15Minimax
            if name in ["v16", "v16_minimax"]:
                module = __import__("p03_minmax.agents.internal.v16_minimax", fromlist=["HeuristicV16Minimax"])
                return module.HeuristicV16Minimax
            if name in ["v17", "v17_minimax", "v17_minimax_hybrid"]:
                module = __import__("p03_minmax.agents.internal.v17_minimax_hybrid", fromlist=["HeuristicV17MinimaxHybrid"])
                return module.HeuristicV17MinimaxHybrid
            if name in ["v18", "v18_mcts"]:
                module = __import__("p04_mcts.agents.internal.v18_mcts", fromlist=["HeuristicV18MCTS"])
                return module.HeuristicV18MCTS
            if name in ["v19", "v19_mcts"]:
                module = __import__("p04_mcts.agents.internal.v19_mcts", fromlist=["HeuristicV19MCTS"])
                return module.HeuristicV19MCTS
            if name in ["v20", "v20_mcts", "v20_mcts_hybrid"]:
                module = __import__("p04_mcts.agents.internal.v20_mcts_hybrid", fromlist=["HeuristicV20MCTSHybrid"])
                return module.HeuristicV20MCTSHybrid
            if name in ["v21", "v21_xgboost", "ml_advanced"]:
                module = __import__("p02_imitation_learning.s04_agent.v21_xgboost", fromlist=["HeuristicV21XGBoost"])
                return module.HeuristicV21XGBoost
            
            # Handle standard heuristics v1-v14 (with optional _heuristic suffix)
            clean_name = name.split("_")[0] if "_" in name and name.split("_")[0][1:].isdigit() else name
            version = int(clean_name[1:])
            if 1 <= version <= 14:
                module = __import__(f"p01_heuristics.agents.internal.v{version}", fromlist=[f"HeuristicV{version}"])
                return getattr(module, f"HeuristicV{version}")
        except ValueError:
            pass
            
    if name == "ml_baseline":
        module = __import__("p02_imitation_learning.s04_agent.ml_baseline", fromlist=["MLBaselineAgent"])
        return module.MLBaselineAgent
    if name in ["ml_advanced", "v21_xgboost"]:
        module = __import__("p02_imitation_learning.s04_agent.v21_xgboost", fromlist=["HeuristicV21XGBoost"])
        return module.HeuristicV21XGBoost

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
