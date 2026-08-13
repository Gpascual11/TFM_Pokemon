import glob
import os
import pandas as pd
import numpy as np

def analyze_v1_matchups():
    files = sorted(glob.glob('data/benchmarks/all_10k/gen9randombattle/v1_vs_*.csv'))
    print(f'=== ANALYZING {len(files)} MATCHUP FILES FOR v1 ===\n')

    total_issues = 0
    for f in files:
        df = pd.read_csv(f)
        fname = os.path.basename(f)
        issues = []
        
        # 1. Row count check
        target_rows = 1000 if any(m in fname for m in ['v18', 'v19', 'v20']) else 10000
        if len(df) != target_rows:
            issues.append(f'Expected {target_rows:,} games, found {len(df):,}')
            
        # 2. Null values
        null_counts = df.isnull().sum()
        null_cols = null_counts[null_counts > 0]
        if not null_cols.empty:
            issues.append(f'Nulls found: {null_cols.to_dict()}')
            
        # 3. Invalid wins (must be 0 or 1)
        if 'win' in df.columns:
            invalid_wins = df[~df['win'].isin([0, 1, True, False])]
            if len(invalid_wins) > 0:
                issues.append(f'{len(invalid_wins)} invalid win values')
                
        # 4. Turn counts
        if 'turns' in df.columns:
            bad_turns = df[(df['turns'] <= 0) | (df['turns'] > 300)]
            if len(bad_turns) > 0:
                issues.append(f'{len(bad_turns)} anomalous turn counts (min={df["turns"].min()}, max={df["turns"].max()})')

        # 5. Check infinite / NaN in numeric columns
        num_df = df.select_dtypes(include=[np.number])
        inf_cols = np.isinf(num_df).sum()
        inf_cols = inf_cols[inf_cols > 0]
        if not inf_cols.empty:
            issues.append(f'Infinite values in: {inf_cols.to_dict()}')

        if issues:
            print(f'❌ {fname}:')
            for iss in issues:
                print(f'   - {iss}')
            total_issues += len(issues)
        else:
            print(f'✅ {fname}: Clean ({len(df):,} games)')

    if total_issues == 0:
        print('\n🎉 All v1 CSV datasets analyzed cleanly.')

if __name__ == '__main__':
    analyze_v1_matchups()
