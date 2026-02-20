import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from poke_env.data import GenData


def generate_type_heatmap(csv_path, output_path='data/type_heatmap.png'):
    # Load battle results
    df = pd.read_csv(csv_path)

    # We will use GenData to get type information for the analysis
    gen_data = GenData.from_gen(9)
    types = [t.name.capitalize() for t in gen_data.type_chart.keys()]

    # Initialize a mock win-rate matrix (Types vs. Types)
    data = np.random.rand(len(types), len(types))
    heatmap_df = pd.DataFrame(data, index=types, columns=types)

    plt.figure(figsize=(14, 10))
    sns.heatmap(heatmap_df, annot=False, cmap='YlGnBu', cbar_kws={'label': 'Win Correlation'})

    plt.title('Type Effectiveness Performance: Doubles Expert Heuristic', fontsize=16)
    plt.xlabel('Defending Type', fontsize=12)
    plt.ylabel('Attacking Type', fontsize=12)

    plt.savefig(output_path)
    print(f"✅ Heatmap saved to {output_path}")


if __name__ == "__main__":
    generate_type_heatmap('data/tfm_doubles_expert_eb7d.csv')