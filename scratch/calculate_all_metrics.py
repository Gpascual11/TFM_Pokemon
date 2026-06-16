import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path("/home/sirp/Documents/MUDS/TFM_Pokemon/data/benchmarks/all_10k")
REPORT_DIR = Path("/home/sirp/Documents/MUDS/TFM_Pokemon/report")

# Define the exact 18 agents in order of strength/lineage for rows/cols
AGENT_ORDER = [
    "v12", "v11", "v10", "v9", "v8", "v7", "v6", "v5", "v4", "v3", "v2", "v1",
    "simple_heuristic", "abyssal", "safe_one_step", "one_step", "max_power", "random"
]

DISPLAY_NAMES = {
    "v12": "(H) v12", "v11": "(H) v11", "v10": "(H) v10", "v9": "(H) v9", "v8": "(H) v8",
    "v7": "(H) v7", "v6": "(H) v6", "v5": "(H) v5", "v4": "(H) v4", "v3": "(H) v3",
    "v2": "(H) v2", "v1": "(H) v1", "simple_heuristic": "(B) simple\\_heuristic",
    "abyssal": "(C) abyssal", "safe_one_step": "(C) safe\\_one\_step", "one_step": "(C) one\\_step",
    "max_power": "(B) max\\_power", "random": "(B) random"
}

def get_display(name):
    return DISPLAY_NAMES.get(name, name.replace("_", "\\_"))

def process_file_gen9(f_path):
    parts = f_path.stem.split("_vs_")
    if len(parts) != 2:
        return None
    agent, opponent = parts[0], parts[1]
    
    cols = ['won', 'turns', 'fainted_us', 'fainted_opp']
    try:
        df = pd.read_csv(f_path, usecols=cols)
        games = len(df)
        wins = df['won'].sum()
        turns = df['turns'].sum()
        f_us = df['fainted_us'].sum()
        f_opp = df['fainted_opp'].sum()
        return {
            'agent': agent,
            'opponent': opponent,
            'games': games,
            'wins': wins,
            'turns': turns,
            'fainted_us': f_us,
            'fainted_opp': f_opp
        }
    except Exception as e:
        print(f"Error {f_path.name}: {e}")
        return None

def process_file_other_gen(f_path):
    parts = f_path.stem.split("_vs_")
    if len(parts) != 2:
        return None
    agent, opponent = parts[0], parts[1]
    try:
        df = pd.read_csv(f_path, usecols=['won'])
        games = len(df)
        wins = df['won'].sum()
        return {
            'agent': agent,
            'opponent': opponent,
            'games': games,
            'wins': wins
        }
    except Exception as e:
        print(f"Error {f_path.name}: {e}")
        return None

def calculate_bt_elo(df_format, anchor_agent="random", anchor_elo=1000, max_iter=500, tol=1e-8):
    agents = sorted(list(set(df_format['agent']).union(set(df_format['opponent']))))
    n_agents = len(agents)
    agent_to_idx = {name: i for i, name in enumerate(agents)}
    
    W = np.zeros((n_agents, n_agents))
    N = np.zeros((n_agents, n_agents))
    
    for _, row in df_format.iterrows():
        u = agent_to_idx[row['agent']]
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

def main():
    print("🚀 Starting full tournament analysis...")
    
    # 1. Calculate Elo for all generations
    all_elos = {}
    pool = multiprocessing.Pool(processes=8)
    
    for gen_num in range(1, 10):
        gen = f"gen{gen_num}randombattle"
        gen_dir = DATA_DIR / gen
        csv_files = [f for f in gen_dir.glob("*.csv") if f.name not in ["elo_summary.csv", "matchup_performance.csv"]]
        
        print(f"Processing {gen} ({len(csv_files)} files)...")
        if gen_num == 9:
            results = pool.map(process_file_gen9, csv_files)
        else:
            results = pool.map(process_file_other_gen, csv_files)
            
        results = [r for r in results if r is not None]
        df_gen = pd.DataFrame(results)
        
        # Calculate Bradley-Terry Elo
        df_elo = calculate_bt_elo(df_gen)
        all_elos[gen] = df_elo.set_index('Agent')['Elo']
        
        # For Gen 9, save additional matrices
        if gen_num == 9:
            # We want matrices for Win Rate, Fainted Diff, and Turns
            # We pivot the results
            df_g9 = df_gen.copy()
            
            # Make sure we have both directions represented for completeness
            # Since some runs are one-way or symmetric
            # In our round robin, we have both a_vs_b and b_vs_a files
            # Let's aggregate by agent & opponent
            
            # Win Rate Matrix
            df_g9['win_rate'] = (df_g9['wins'] / df_g9['games']) * 100.0
            wr_pivot = df_g9.pivot(index='agent', columns='opponent', values='win_rate')
            wr_pivot = wr_pivot.reindex(index=AGENT_ORDER, columns=AGENT_ORDER)
            
            # Fainted Diff Matrix: (fainted_opp - fainted_us) / games
            df_g9['fainted_diff'] = (df_g9['fainted_opp'] - df_g9['fainted_us']) / df_g9['games']
            fd_pivot = df_g9.pivot(index='agent', columns='opponent', values='fainted_diff')
            fd_pivot = fd_pivot.reindex(index=AGENT_ORDER, columns=AGENT_ORDER)
            
            # Output Gen 9 Win Rate Table
            wr_tex_path = REPORT_DIR / "tables/singles_gen9_wr.tex"
            with open(wr_tex_path, "w") as f:
                f.write("\\begin{table}[htbp]\n")
                f.write("\\caption{Matriu de Win-Rate (\%) - Singles Gen 9}\n")
                f.write("\\label{tab:win_rate_matrix}\n")
                f.write("\\begin{adjustbox}{width=\\linewidth,center}\n")
                f.write("\\begin{tabular}{l" + "c" * len(AGENT_ORDER) + "}\n")
                f.write("\\hline\n")
                f.write(" & " + " & ".join([get_display(a) for a in AGENT_ORDER]) + " \\\\\n")
                f.write("\\hline\n")
                for agent in AGENT_ORDER:
                    row_strs = []
                    for opp in AGENT_ORDER:
                        val = wr_pivot.loc[agent, opp]
                        if pd.isna(val):
                            row_strs.append("-")
                        else:
                            row_strs.append(f"{val:.1f}")
                    f.write(f"{get_display(agent)} & " + " & ".join(row_strs) + " \\\\\n")
                f.write("\\hline\n")
                f.write("\\end{tabular}\n")
                f.write("\\end{adjustbox}\n")
                f.write("\\end{table}\n")
            print(f"✓ Saved Win Rate matrix to {wr_tex_path}")
            
            # Output Gen 9 Fainted Diff Table
            fd_tex_path = REPORT_DIR / "tables/singles_gen9_fainted.tex"
            with open(fd_tex_path, "w") as f:
                f.write("\\begin{table}[htbp]\n")
                f.write("\\caption{Diferencial Mitjà de Pokémon Derrotats (Rival - Propi) - Singles Gen 9}\n")
                f.write("\\label{tab:fainted_diff}\n")
                f.write("\\begin{adjustbox}{width=\\linewidth,center}\n")
                f.write("\\begin{tabular}{l" + "c" * len(AGENT_ORDER) + "}\n")
                f.write("\\hline\n")
                f.write(" & " + " & ".join([get_display(a) for a in AGENT_ORDER]) + " \\\\\n")
                f.write("\\hline\n")
                for agent in AGENT_ORDER:
                    row_strs = []
                    for opp in AGENT_ORDER:
                        val = fd_pivot.loc[agent, opp]
                        if pd.isna(val):
                            row_strs.append("-")
                        else:
                            row_strs.append(f"{val:+.2f}")
                    f.write(f"{get_display(agent)} & " + " & ".join(row_strs) + " \\\\\n")
                f.write("\\hline\n")
                f.write("\\end{tabular}\n")
                f.write("\\end{adjustbox}\n")
                f.write("\\end{table}\n")
            print(f"✓ Saved Fainted Diff matrix to {fd_tex_path}")

    pool.close()
    pool.join()
    
    # 2. Output Elo Table across all generations
    df_all_elos = pd.DataFrame(all_elos)
    df_all_elos = df_all_elos.reindex(AGENT_ORDER)
    
    # Save the consolidated Elo ratings table in LaTeX format
    elo_tex_path = REPORT_DIR / "tables/elo_singles_gen9.tex"
    with open(elo_tex_path, "w") as f:
        f.write("\\begin{table}[htbp]\n")
        f.write("\\caption{Classificació i Rànquing Elo Bradley-Terry de tots els agents Singles (Generacions 1--9)}\n")
        f.write("\\label{tab:elo_singles_all_gens}\n")
        f.write("\\begin{adjustbox}{width=\\linewidth,center}\n")
        f.write("\\begin{tabular}{lccccccccc}\n")
        f.write("\\hline\n")
        f.write("Agent & Gen 1 & Gen 2 & Gen 3 & Gen 4 & Gen 5 & Gen 6 & Gen 7 & Gen 8 & Gen 9 \\\\\n")
        f.write("\\hline\n")
        for agent in AGENT_ORDER:
            row_strs = []
            for g_num in range(1, 10):
                val = df_all_elos.loc[agent, f"gen{g_num}randombattle"]
                if pd.isna(val):
                    row_strs.append("-")
                else:
                    row_strs.append(f"{int(round(val))}")
            f.write(f"{get_display(agent)} & " + " & ".join(row_strs) + " \\\\\n")
        f.write("\\hline\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{adjustbox}\n")
        f.write("\\end{table}\n")
    print(f"✓ Saved Consolidated Elo Table to {elo_tex_path}")
    
    # Let's print out Gen 9 Elo rankings to console
    print("\n=== Bradley-Terry Elo Rankings (Gen 9) ===")
    print(df_all_elos['gen9randombattle'].round(1).to_string())

if __name__ == "__main__":
    main()
