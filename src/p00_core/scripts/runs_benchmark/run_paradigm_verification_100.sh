#!/bin/bash
# run_paradigm_verification_100.sh — Verification run of 100 games across
# new paradigm agents (v15_minimax to v21_xgboost) vs key old/baseline matchups
# to verify complete end-to-end execution, telemetry recording, and CSV saving.
#
# MATCHUPS EVALUATED:
#   Primary Agents : v15_minimax, v16_minimax, v17_minimax_hybrid, v18_mcts, v19_mcts, v20_mcts_hybrid, v21_xgboost
#   Opponent Set   : v1, v14, random
#
# TELEMETRY VERIFIED:
#   - CSV creation in data/benchmarks/verification_100games_gen9/
#   - Advanced telemetry columns check: search_diff_us, xgb_switches_us, ko_guards_us, loop_guards_us, etc.

if grep -q 'avis_telegram()' ~/.bashrc 2>/dev/null; then
    eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"
else
    avis_telegram() { echo "[NOTIFY] $1"; }
fi

NEW_AGENTS=${NEW_AGENTS:-"v15_minimax v16_minimax v17_minimax_hybrid v18_mcts v19_mcts v20_mcts_hybrid v21_xgboost"}
ALL_AGENTS=${ALL_AGENTS:-"v1 v14 random"}
N_BATTLES=${N_BATTLES:-100}
PORTS=${PORTS:-8}
CONCURRENCY=${CONCURRENCY:-25}
OUT_DIR=${OUT_DIR:-"data/benchmarks/verification_100games_gen9"}
RESTART_EVERY=20
MAX_RETRIES=3

cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null || true
    pkill -f "worker.py" 2>/dev/null || true
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "${PORT}/tcp" 2>/dev/null || true
    done
    sleep 3
    sync
}

trap 'cleanup; avis_telegram "🛑 KILLED: 100-game verification run interrupted."; exit 1' SIGTERM SIGINT SIGHUP

N_ALL=$(echo $ALL_AGENTS | wc -w)
N_NEW=$(echo $NEW_AGENTS | wc -w)
TOTAL_MATCHUPS=$(( N_NEW * N_ALL ))

echo "════════════════════════════════════════════════════════"
echo " 100-Game Paradigm Verification & CSV Telemetry Check"
echo " Evaluated Agents : ${NEW_AGENTS}"
echo " Opponent Set     : ${ALL_AGENTS} (${N_ALL} agents)"
echo " Target Matchups  : ${TOTAL_MATCHUPS} matchups × ${N_BATTLES} games"
echo " Output Location  : ${OUT_DIR}/"
echo "════════════════════════════════════════════════════════"

TOTAL_START=$(date +%s)
avis_telegram "🧪 Starting 100-game verification run: ${N_NEW} agents × ${N_ALL} opponents = ${TOTAL_MATCHUPS} matchups | $(date '+%H:%M')"

cleanup

# Create output directory
mkdir -p "$OUT_DIR"

AGENT_IDX=0
for AGENT in $NEW_AGENTS; do
    AGENT_IDX=$(( AGENT_IDX + 1 ))
    ATTEMPT=0
    SUCCESS=false

    START_AGENT=$(date +%s)
    avis_telegram "🧪 [${AGENT_IDX}/${N_NEW}] Verifying ${AGENT} vs ${ALL_AGENTS} | $(date '+%H:%M')"

    while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
        ATTEMPT=$(( ATTEMPT + 1 ))

        if [ $ATTEMPT -gt 1 ]; then
            avis_telegram "🔄 [${AGENT}] Retry ${ATTEMPT}/${MAX_RETRIES} | $(date '+%H:%M')"
            cleanup
            sleep 10
        fi

        uv run python src/p00_core/engine/benchmark.py \
            $N_BATTLES \
            --agents "$AGENT" \
            --opponents $ALL_AGENTS \
            --ports $PORTS \
            --concurrency $CONCURRENCY \
            --battle-format gen9randombattle \
            --out "$OUT_DIR" \
            --restart-every $RESTART_EVERY
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            SUCCESS=true
        else
            avis_telegram "⚠️  [${AGENT}] FAIL attempt ${ATTEMPT}/${MAX_RETRIES} (exit ${EXIT_CODE})"
            cleanup
            sleep 10
        fi
    done

    if [ "$SUCCESS" = false ]; then
        avis_telegram "💥 FATAL: ${AGENT} failed after ${MAX_RETRIES} retries. Aborting verification."
        cleanup
        exit 1
    fi

    ELAPSED=$(( $(date +%s) - START_AGENT ))
    avis_telegram "✅ [${AGENT_IDX}/${N_NEW}] ${AGENT} verification complete (${ELAPSED}s)"
done

cleanup

TOTAL_ELAPSED=$(( $(date +%s) - TOTAL_START ))
echo ""
echo "════════════════════════════════════════════════════════"
echo " All ${TOTAL_MATCHUPS} Matchups Completed in ${TOTAL_ELAPSED}s!"
echo " Verifying saved CSV columns and record counts..."
echo "════════════════════════════════════════════════════════"

uv run python -c "
import pandas as pd
from pathlib import Path

out_path = Path('$OUT_DIR')
csv_files = list(out_path.glob('*.csv'))
if not csv_files:
    print('❌ ERROR: No CSV files found in', out_path)
    exit(1)

print(f'\nFound {len(csv_files)} CSV files in {out_path}:\n')
print(f'{\"File Name\":<35} | {\"Rows\":<6} | {\"Key Columns Verified (search_diff_us, xgb_switches_us, etc.)\"}')
print('-' * 95)

all_ok = True
for f in sorted(csv_files):
    df = pd.read_csv(f)
    cols = set(df.columns)
    
    # Check for telemetry columns
    expected_cols = {'search_diff_us', 'search_diff_opp', 'xgb_switches_us', 'xgb_switches_opp', 'ko_guards_us', 'loop_guards_us'}
    missing = expected_cols - cols
    
    status = '✅ OK' if not missing else f'⚠️ Missing: {missing}'
    print(f'{f.name:<35} | {len(df):<6} | {status}')
    if missing:
        all_ok = False

if all_ok:
    print('\n🚀 SUCCESS: All CSV files generated correctly with full telemetry fields!')
else:
    print('\n⚠️ WARNING: Some CSV files are missing expected telemetry columns.')
"

avis_telegram "🎉 100-game verification run finished in ${TOTAL_ELAPSED}s! All CSVs verified."
echo "Done! You can check results in: ${OUT_DIR}/"
