"""Internal heuristics benchmark sub-package.

Contains the tools for running round-robin tournaments between the
internal heuristic versions (v1–v6) and baseline opponents using
the standard poke_env server infrastructure.

Entry points
------------
run.py
    Quick single-matchup simulation.
benchmark.py
    Full automated round-robin benchmark with checkpointing.
generate_report.py
    Visual PNG report from benchmark results.
"""
