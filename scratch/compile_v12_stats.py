import os
import pandas as pd

gens = ["gen9randombattle", "gen5randombattle", "gen1randombattle"]
opponents = ["random", "v7", "v10", "v8", "v9", "v11", "abyssal", "simple_heuristic"]

for gen in gens:
    print(f"\n### {gen} Results")
    print("| Opponent | Win Rate % | Avg Turns | Vol. Switches | Matchup Sw. | Errors Us |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: |")
    
    # We want to order by win rate descending to match the walkthrough table style
    rows = []
    for opp in opponents:
        csv_path = f"data/1_vs_1/benchmarks_v12_10k/{gen}/v12_vs_{opp}.csv"
        if not os.path.exists(csv_path):
            continue
        df = pd.read_csv(csv_path)
        
        wr = df["won"].mean() * 100
        avg_turns = df["turns"].mean()
        vol_sw = df["voluntary_switches_us"].mean()
        matchup_sw = df["matchup_switches_us"].mean()
        errors = df["error_moves_us"].sum()
        
        rows.append({
            "opp": opp,
            "wr": wr,
            "avg_turns": avg_turns,
            "vol_sw": vol_sw,
            "matchup_sw": matchup_sw,
            "errors": errors
        })
    
    # Sort rows by win rate descending
    rows.sort(key=lambda x: x["wr"], reverse=True)
    
    for r in rows:
        print(f"| **{r['opp']}** | **{r['wr']:.1f}%** | {r['avg_turns']:.2f} | {r['vol_sw']:.2f} | {r['matchup_sw']:.2f} | {r['errors']:.2f} |")
