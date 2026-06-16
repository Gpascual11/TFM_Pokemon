# core: Heuristic Infrastructure (Singles)

This is the internal "engine" that runs the heuristic agents. It is designed to be highly reliable, supporting long-running parallel benchmarks.

## Modules

- `base.py`: The abstract `BaseHeuristic1v1` class. All agents inherit from here.
- `common.py`: Math and Pokédex utility functions (e.g. speed-tie calculation).
- `factory.py`: The Factory pattern that lets us instantiate agents via labels (e.g. "v6").
- `battle_manager.py`: Orchestrates the connection to a single Showdown server and manages a battle queue.
- `process_launcher.py`: High-level utility to distribute battles across multiple CPU processes and Showdown servers in parallel.

## Robustness Features
- **Worker Isolation**: Each batch of games runs in a fresh process that dies upon completion, effectively clearing all Python memory leaks.
- **Server Purging**: Showdown servers are restarted between matchups to clear Node.js memory leaks.
- **CSV Merging**: Parallel results are automatically merged into a single consistent dataset.
