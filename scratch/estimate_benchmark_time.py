import os

def estimate_remaining_time():
    benchmark_dir = 'data/benchmarks/all_10k/gen9randombattle'
    files = os.listdir(benchmark_dir)
    completed = {}

    for f in files:
        if f.endswith('.csv'):
            name = f[:-4]
            path = os.path.join(benchmark_dir, f)
            with open(path, 'rb') as fp:
                c_lines = sum(1 for _ in fp) - 1
            completed[name] = max(0, c_lines)

    agents = 'v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 v17 v18 v19 v20 v21 v22 random max_power abyssal one_step safe_one_step simple_heuristic'.split()
    mcts_set = {'v18', 'v19', 'v20'}

    tot_matchups = len(agents) * len(agents)
    done_matchups = 0
    rem_fast_games = 0
    rem_mcts_games = 0

    for a in agents:
        for o in agents:
            target = 1000 if (a in mcts_set or o in mcts_set) else 10000
            key = f'{a}_vs_{o}'
            done = completed.get(key, 0)
            if done >= target:
                done_matchups += 1
            else:
                rem = target - done
                if a in mcts_set or o in mcts_set:
                    rem_mcts_games += rem
                else:
                    rem_fast_games += rem

    # Throughput estimates (games/sec across parallel workers):
    # Fast & Minimax (25 concurrency): ~90 games/sec
    # MCTS (20 concurrency): ~8 games/sec
    time_fast_sec = rem_fast_games / 90.0
    time_mcts_sec = rem_mcts_games / 8.0
    total_sec = time_fast_sec + time_mcts_sec

    hours = int(total_sec // 3600)
    mins = int((total_sec % 3600) // 60)

    print(f'Total Matchups in Matrix       : {tot_matchups}')
    print(f'Already Completed Matchups     : {done_matchups} / {tot_matchups}')
    print(f'Remaining Fast/Minimax Games   : {rem_fast_games:,}')
    print(f'Remaining MCTS Games           : {rem_mcts_games:,}')
    print(f'Estimated Fast/Minimax Time    : {int(time_fast_sec//3600)}h {int((time_fast_sec%3600)//60)}m')
    print(f'Estimated MCTS Time            : {int(time_mcts_sec//3600)}h {int((time_mcts_sec%3600)//60)}m')
    print(f'ESTIMATED TOTAL REMAINING TIME : {hours}h {mins}m')

if __name__ == '__main__':
    estimate_remaining_time()
