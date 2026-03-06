# LLM Agents Directory

This directory is intentionally empty.

The LLM agents for the heuristics engine (`pokechamp`, `pokellmon`) are **not** implemented directly within this `s01_singles/agents/llm` or `s02_doubles/agents/llm` folders.

Instead, they are dynamically loaded from the external `pokechamp` repository hook.

## How it works

When you request the `pokechamp` or `pokellmon` agents in the benchmark, the `AgentFactory` (`src/p01_heuristics/s01_singles/core/factory.py`) natively detects these identifiers.

It then dynamically links to the `pokechamp` repository cloned at the root of your TFM directory, and imports `get_llm_player` from pokechamp's custom `poke_env` fork.

This architecture ensures we can evaluate the paper's original LLM agents alongside our custom heuristics without having to duplicate or manually sync their complex PyTorch and transformers codebase.

To configure how these LLM agents operate, please read the [LLM Setup Guide](../../evaluation/docs/LLM_SETUP_GUIDE.md).
