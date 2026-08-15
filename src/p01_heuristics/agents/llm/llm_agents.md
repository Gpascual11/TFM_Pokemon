# LLM Agents Directory

`pokechamp` and `pokellmon` load from the `pokechamp` repository hook at the project root. `AgentFactory` (`src/p00_core/core/factory.py`) maps those identifiers to `get_llm_player` in pokechamp’s `poke_env` fork.

That keeps the paper’s original LLM agents evaluable next to the custom heuristics without duplicating their PyTorch stack.

To configure how these LLM agents operate, please read the [LLM Setup Guide](../../../p00_core/docs/llm_setup_guide.md).

## How it works

When you request the `pokechamp` or `pokellmon` agents in the benchmark, the `AgentFactory` (`src/p00_core/core/factory.py`) natively detects these identifiers.

It then dynamically links to the `pokechamp` repository cloned at the root of your TFM directory, and imports `get_llm_player` from pokechamp's custom `poke_env` fork.

This architecture ensures we can evaluate the paper's original LLM agents alongside our custom heuristics without having to duplicate or manually sync their complex PyTorch and transformers codebase.

To configure how these LLM agents operate, please read the [LLM Setup Guide](../../../p00_core/docs/llm_setup_guide.md).
