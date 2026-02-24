# core: Heuristic Infrastructure (Singles)

This is the internal "engine" that runs the heuristic agents.

## Modules

- `base.py`: The abstract `BaseHeuristic1v1` class. All agents inherit from here.
- `common.py`: Math and Pokédex utility functions (e.g. speed-tie calculation).
- `factory.py`: The Pattern that lets us choose "v6" via command line.
- `battle_manager.py`: The loop that connects to the server and feeds battles to the player.
- `process_launcher.py`: Utility to start multiple Python instances for parallel testing.
