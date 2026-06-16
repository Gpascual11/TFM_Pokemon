from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path("/home/sirp/Documents/MUDS/TFM_Pokemon/data/benchmarks/all_10k")

def calculate_bt_elo(df_format, anchor_agent="random", anchor_elo=1000, max_iter=300, tol=1e-6):
    agents = sorted(list(set(df_format['heuristic']).union(set(df_format['opponent']))))
    n_agents = len(agents)
    agent_to_idx = {name: i for i, name in enumerate(agents)}
    
    W = np.zeros((n_agents, n_agents))
    N = np.zeros((n_agents, n_agents))
    
    for _, row in df_format.iterrows():
        u = agent_to_idx[row['heuristic']]
        o = agent_to_idx[row['opponent']]
        W[u, o] += row['wins']
        N[u, o] += row['games']
        W[o, u] += (row['games'] - row['wins'])
        N[o, u] += row['games']
        
    pi = np.ones(n_agents)
    for _ in range(max_iter):
        pi_old = pi.copy()
        for i in range(n_agents):
            denom = 0.0
            for j in range(n_agents):
                if N[i, j] > 0:
                    denom += N[i, j] / (pi[i] + pi[j])
            if denom > 0:
                pi[i] = np.sum(W[i, :]) / denom
        pi /= np.mean(pi)
        if np.max(np.abs(pi - pi_old)) < tol:
            break
            
    elo = 400 * np.log10(pi)
    if anchor_agent in agent_to_idx:
        shift = anchor_elo - elo[agent_to_idx[anchor_agent]]
        elo += shift
        
    return pd.DataFrame({
        'Agent': agents,
        'Elo': elo
    })

# Load and aggregate data
gens = [f"gen{i}randombattle" for i in range(1, 10)]
all_elo_data = {}

for gen in gens:
    gen_dir = DATA_DIR / gen
    csv_files = list(gen_dir.glob("*.csv"))
    csv_files = [f for f in csv_files if f.name not in ["elo_summary.csv", "matchup_performance.csv"]]
    
    records = []
    for f in csv_files:
        # We need opponent name and won/games
        # Files are named like: agent_vs_opponent.csv
        parts = f.stem.split("_vs_")
        if len(parts) != 2:
            continue
        agent, opponent = parts[0], parts[1]
        
        try:
            df = pd.read_csv(f, usecols=['won'])
            games = len(df)
            wins = df['won'].sum()
            records.append({
                'heuristic': agent,
                'opponent': opponent,
                'wins': wins,
                'games': games
            })
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    df_gen = pd.DataFrame(records)
    if not df_gen.empty:
        df_elo = calculate_bt_elo(df_gen)
        # Sort and store
        all_elo_data[gen] = df_elo.set_index('Agent')['Elo']

df_all_elos = pd.DataFrame(all_elo_data)
# Reorder index based on average Elo or heuristic lineage
agent_order = [f"v{i}" for i in range(12, 0, -1)] + ["simple_heuristic", "abyssal", "safe_one_step", "one_step", "max_power", "random"]
df_all_elos = df_all_elos.reindex(agent_order)
print(df_all_elos.round(1).to_string())
