"""Pokechamp cross-repository benchmark sub-package.

Orchestrates tournaments between Pokechamp/Pokellmon LLM agents and the
internal heuristic opponents.  Each battle batch runs in an isolated
subprocess so the OS reclaims all memory used by Pokechamp's background
``POKE_LOOP`` thread after every batch.

Entry points
------------
pokechamp_benchmark.py
    Main orchestrator — spawns worker subprocesses, merges CSVs.
_pokechamp_worker.py
    Subprocess worker — runs N battles and exits.
generate_pokechamp_report.py
    Per-agent visual PNG report.
generate_pokechamp_full_report.py
    Full cross-agent comparative report.
"""
