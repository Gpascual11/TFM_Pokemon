"""Unified Factory for instantiating ANY Pokémon agent by name string.
Supports internal heuristics, poke_env baselines, and Pokechamp LLM agents.

This module serves as the Dependency Injection hub for the entire project,
shielding the battle execution loops from complex import paths and disparate
agent initialization signatures.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure we can find the agents relative to this core folder
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Pokechamp root for LLM agents
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"
if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))

from ..agents import get_agent_class


class AgentFactory:
    """Unified Factory for building any Pokémon agent by its name label.

    This factory centralizes the creation of three distinct agent families:
    1. Internal Heuristics (v1-v6): Rule-based experts built locally.
    2. Baselines (abyssal, random, etc.): Standard poke-env agents.
    3. LLM Agents (pokechamp, pokellmon): Model-based agents requiring the Pokechamp library.

    It serves as the main dependency injection point for evaluation scripts.
    """

    @staticmethod
    def available_internal() -> list[str]:
        """Return a list of locally developed rule-based heuristic agents."""
        return ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10"]

    @staticmethod
    def available_baselines() -> list[str]:
        """Return a list of standard baseline agents provided by poke-env."""
        return ["random", "max_power", "abyssal", "one_step", "safe_one_step", "simple_heuristic"]

    @staticmethod
    def available_llm() -> list[str]:
        """Return a list of LLM-based agents relying on the pokechamp library."""
        return ["pokechamp", "pokellmon", "llm_vgc"]

    @staticmethod
    def create(name: str, **kwargs: Any) -> Any:
        """Instantiate the agent identified by *name*.

        This method handles the routing and configuration normalization for all
        agent types. It determines if an agent requires the external `pokechamp`
        library, injects the necessary system paths, and formats the kwargs
        to match what the underlying agent's constructor expects.

        :param name: Label like 'v5', 'abyssal', or 'pokechamp'.
        :param kwargs: Forwarded to the player constructor.
        :return: An instantiated Player object ready for battle.
        :raises ValueError: If the agent name cannot be resolved.
        """
        # Special handling for agents which require the pokechamp library fork
        # Because pokechamp is heavily customized, we prepend it to sys.path
        # only when absolutely necessary to avoid conflicts with standard poke_env.
        if name in ["pokechamp", "pokellmon", "abyssal", "simple_heuristic"]:
            # Ensure pokechamp is in path
            root = Path(__file__).parent.parent.parent.parent.parent.resolve()
            pokechamp_path = root / "pokechamp"
            if pokechamp_path.exists() and str(pokechamp_path) not in sys.path:
                sys.path.insert(0, str(pokechamp_path))

        if name in ["pokechamp", "pokellmon", "llm_vgc"]:
            import argparse

            from poke_env.player.team_util import get_llm_player

            # Extract LLM specific args or use defaults.
            # get_llm_player expects an argparse Namespace for compatibility
            # with legacy execution scripts in the pokechamp repository.
            temperature = kwargs.pop("temperature", 0.3)
            log_dir = kwargs.pop("log_dir", "./battle_log")
            backend = kwargs.pop("backend", "ollama/qwen3:8b")
            prompt_algo = kwargs.pop("prompt_algo", "io")
            tag = kwargs.pop("tag", "0")
            battle_format = kwargs.get("battle_format", "gen9randombattle")

            ns = argparse.Namespace(temperature=temperature, log_dir=log_dir)
            return get_llm_player(
                ns,
                backend=backend,
                prompt_algo=prompt_algo,
                name=name,
                battle_format=battle_format,
                PNUMBER1=tag,
                use_timeout=False,
            )

        # Standard heuristics/baselines cleanup.
        # We must strip LLM-specific parameters to prevent __init__ kwargs errors.
        kwargs.pop("tag", None)
        kwargs.pop("log_dir", None)
        kwargs.pop("temperature", None)
        kwargs.pop("backend", None)
        kwargs.pop("prompt_algo", None)

        cls = get_agent_class(name)
        return cls(**kwargs)


# Alias for backward compatibility
HeuristicFactory = AgentFactory
