import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os


def load_and_clean(csv_path, label):
    df = pd.read_csv(csv_path)
    df['run_type'] = label
    return df


def plot_comparison(df_combined, output_path="../data/comparison_plot.png"):
    plt.figure(figsize=(12, 6))

    # Histogram for Turn Distribution
    sns.histplot(data=df_combined, x='turns', hue='run_type', kde=True, element="step", palette="viridis")

    plt.title('Comparison of Battle Duration: Heuristic vs. Random vs. Self-Play', fontsize=15)
    plt.xlabel('Number of Turns', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.grid(axis='y', alpha=0.3)

    plt.savefig(output_path)
    plt.show()


def create_tfm_boxplot(df_combined):
    # 1. Ensure the directory exists to avoid FileNotFoundError
    os.makedirs("data", exist_ok=True)

    plt.figure(figsize=(10, 6))

    # 2. Create the Box Plot
    # A Box Plot is better for your thesis to show outliers (the long tail)
    sns.boxplot(data=df_combined, x='run_type', y='turns', palette="Set2")

    plt.title('Statistical Distribution of Battle Turns', fontsize=14)
    plt.xlabel('Experiment Type', fontsize=12)
    plt.ylabel('Number of Turns', fontsize=12)

    # 3. Save and Show
    save_path = "../data/tfm_boxplot_comparison.png"
    plt.savefig(save_path)
    print(f" Boxplot saved successfully at: {save_path}")
    plt.show()


def get_statistics(df_combined):
    stats = df_combined.groupby('run_type')['turns'].agg(['mean', 'std', 'min', 'max', 'count']).reset_index()
    # Calculate Win Rate specifically
    win_rates = df_combined.groupby('run_type')['won'].mean() * 100
    stats['win_rate_%'] = stats['run_type'].map(win_rates)
    return stats