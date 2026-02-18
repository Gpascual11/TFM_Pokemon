import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import os


def compare_singles_doubles(singles_path, doubles_path):
    # Load data
    df_s = pd.read_csv(singles_path)
    df_d = pd.read_csv(doubles_path)

    df_s['format'] = 'Singles (1vs1)'
    df_d['format'] = 'Doubles (2vs2)'
    df_all = pd.concat([df_s, df_d])

    # 1. Statistical Summary
    stats_data = []
    for name, df in [("Singles", df_s), ("Doubles", df_d)]:
        mean_t = df['turns'].mean()
        std_t = df['turns'].std()

        # 95% Confidence Interval for mean turns
        ci = stats.t.interval(0.95, len(df) - 1, loc=mean_t, scale=stats.sem(df['turns']))

        stats_data.append({
            "Format": name,
            "Mean Turns": round(mean_t, 2),
            "SD": round(std_t, 2),
            "95% CI (Turns)": f"[{ci[0]:.2f}, {ci[1]:.2f}]",
            "Win Rate (%)": round(df['won'].mean() * 100, 2)
        })


    plt.figure(figsize=(12, 6))
    sns.kdeplot(data=df_all, x='turns', hue='format', fill=True, common_norm=False, palette='viridis')
    plt.title('Battle Duration Distribution: Singles vs. Doubles Expert Heuristic', fontsize=15)
    plt.xlabel('Number of Turns', fontsize=12)
    plt.ylabel('Density', fontsize=12)
    plt.grid(axis='y', alpha=0.3)

    os.makedirs('data', exist_ok=True)
    plt.savefig('data/comparison_distribution.png')
    return pd.DataFrame(stats_data)