#!/bin/bash
# ==============================================================================
# Master Paradigm Evaluation Runner: run_paradigm_comparison_10k.sh
# ------------------------------------------------------------------------------
# Purpose: Executes full 10,000-game comparative round-robin tournament across all
#          master TFM paradigms (Heuristic, Minimax, MCTS, Imitation Learning).
#
# Hardware Optimization: AMD Ryzen 7 5700X3D (8 Ports, Tuned Concurrency)
#
# Usage:
#   bash src/p00_core/scripts/runs_benchmark/run_paradigm_comparison_10k.sh
#   (Auto-tees output live to paradigm_eval.log with zero orphan process overhead)
# ==============================================================================

set -euo pipefail

# ── Internal Log Redirection (Auto-tees output to paradigm_eval.log safely) ──
LOG_PATH="paradigm_eval.log"
if [ "${INTERNAL_LOGGING:-0}" -ne 1 ]; then
    export INTERNAL_LOGGING=1
    exec > >(tee -a "$LOG_PATH") 2>&1
fi

# ── Load credentials from .env ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
ENV_FILE="$ROOT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
else
    echo "⚠️  No .env found — Telegram notifications disabled."
    TELEGRAM_TOKEN=""
    TELEGRAM_CHAT_ID=""
fi

# ── Telegram notification ──────────────────────────────────────────────────────
avis_telegram() {
    if [ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            -d text="$1" >/dev/null 2>&1 || true
    else
        echo "[NOTIFY] $1"
    fi
}

# ── Configuration ──────────────────────────────────────────────────────────────
# Gauntlet of opponents (subset of baseline + main paradigm agents)
# Default is a smaller test gauntlet; override via env vars for the full run:
#   ALL_AGENTS="v1 v8 v12 v14 v15_minimax v16_minimax v17_minimax_hybrid v18_mcts v19_mcts v20_mcts_hybrid v21_xgboost random max_power abyssal"
ALL_AGENTS=${ALL_AGENTS:-"v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 v17 v18 v19 v20 v21 v22 random max_power abyssal one_step safe_one_step simple_heuristic"}

# Main agents under evaluation — setting NEW_AGENTS equal to ALL_AGENTS ensures
# FULL BIDIRECTIONAL ROUND-ROBIN COVERAGE: every pair (A, B) plays both A vs B (10k) AND B vs A (10k).
NEW_AGENTS=${NEW_AGENTS:-"v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 v17 v18 v19 v20 v21 v22 random max_power abyssal one_step safe_one_step simple_heuristic"}

N_BATTLES=${N_BATTLES:-10000}
PORTS=${PORTS:-8}
CONCURRENCY=${CONCURRENCY:-25}
OUT_DIR=${OUT_DIR:-"data/benchmarks/all_10k/gen9randombattle"}
RESTART_EVERY=20    # restart Showdown servers every N matchups to prevent memory bloat
MAX_RETRIES=100

MONITOR_PID=""

# ── Progress & Stuck Monitor (Fast MCTS 25% Thread Restart + 20m Telemetry) ──
start_telegram_monitor() {
    (
        set +e +u
        mkdir -p "$OUT_DIR"
        echo "Monitor started at $(date). OUT_DIR=$OUT_DIR, TELEGRAM_TOKEN_LEN=${#TELEGRAM_TOKEN}, TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID"
        LAST_ROWS=0
        LAST_MATCHUP=""
        TELEM_COUNTER=0
        STALL_COUNTER=0

        while true; do
            sleep 60  # Check every 60 seconds
            TELEM_COUNTER=$(( TELEM_COUNTER + 1 ))

            if [ -d "$OUT_DIR" ]; then
                ACTIVE_FILE=$(ls -t "$OUT_DIR"/_tmp_*.csv 2>/dev/null | head -n 1 || true)
                if [ -n "$ACTIVE_FILE" ]; then
                    MATCHUP_TAG=$(basename "$ACTIVE_FILE" | sed -E 's/_tmp_(.*)_p[0-9]+_b[0-9]+\.csv/\1/')
                    TOTAL_ROWS=$(wc -l "$OUT_DIR"/_tmp_${MATCHUP_TAG}_p*.csv 2>/dev/null | tail -n 1 | awk '{print $1}')
                    NUM_FILES=$(ls "$OUT_DIR"/_tmp_${MATCHUP_TAG}_p*.csv 2>/dev/null | wc -l || echo 0)
                    ACTUAL_ROWS=$(( TOTAL_ROWS - NUM_FILES ))
                    [ $ACTUAL_ROWS -lt 0 ] && ACTUAL_ROWS=0

                    TARGET_N=10000
                    IS_MCTS=false
                    if [[ "$MATCHUP_TAG" =~ (v18|v19|v20) ]]; then
                        TARGET_N=1000
                        IS_MCTS=true
                    fi

                    EXIST_CSV="${OUT_DIR}/${MATCHUP_TAG}.csv"
                    SAVED_GAMES=0
                    if [ -f "$EXIST_CSV" ]; then
                        S_ROWS=$(wc -l < "$EXIST_CSV" 2>/dev/null || echo 0)
                        [ $S_ROWS -gt 0 ] && SAVED_GAMES=$(( S_ROWS - 1 ))
                    fi
                    TOTAL_DONE=$(( SAVED_GAMES + ACTUAL_ROWS ))

                    # ── MCTS Fast-Restart Check: >25% threads finished & rest stalled ──
                    MUST_RESTART=false
                    if [ "$IS_MCTS" = true ] && [ "$NUM_FILES" -gt 0 ]; then
                        MAX_L_CNT=$(wc -l "$OUT_DIR"/_tmp_${MATCHUP_TAG}_p*.csv 2>/dev/null | grep -v "total" | awk '{print $1}' | sort -nr | head -n 1 || echo 0)
                        THRESH=$(( MAX_L_CNT * 85 / 100 ))
                        [ $THRESH -lt 5 ] && THRESH=5

                        FINISHED_THREADS=0
                        for TMP_F in "$OUT_DIR"/_tmp_${MATCHUP_TAG}_p*.csv; do
                            if [ -f "$TMP_F" ]; then
                                L_CNT=$(wc -l < "$TMP_F" 2>/dev/null || echo 0)
                                if [ "$L_CNT" -ge "$THRESH" ] && [ "$MAX_L_CNT" -ge 10 ]; then
                                    FINISHED_THREADS=$(( FINISHED_THREADS + 1 ))
                                fi
                            fi
                        done

                        PCT_FINISHED=$(( (FINISHED_THREADS * 100) / NUM_FILES ))
                        if [ "$PCT_FINISHED" -ge 25 ] && [ "$FINISHED_THREADS" -lt "$NUM_FILES" ]; then
                            if [ "$MATCHUP_TAG" = "$LAST_MATCHUP" ] && [ "$TOTAL_DONE" -eq "$LAST_ROWS" ]; then
                                STALL_COUNTER=$(( STALL_COUNTER + 1 ))
                                if [ "$STALL_COUNTER" -ge 2 ]; then
                                    MUST_RESTART=true
                                    avis_telegram "⚡ [MCTS Fast-Restart] ${MATCHUP_TAG}: ${FINISHED_THREADS}/${NUM_FILES} threads finished (${PCT_FINISHED}% >= 25%). Remaining threads stalled. Merging ${ACTUAL_ROWS} games and restarting..."
                                fi
                            else
                                STALL_COUNTER=0
                            fi
                        else
                            STALL_COUNTER=0
                        fi
                    fi

                    # ── Inactivity Check: Trigger fast-restart if any active thread hasn't written in >10 mins (600s) ──
                    NOW_SEC=$(date +%s)
                    for TMP_F in "$OUT_DIR"/_tmp_${MATCHUP_TAG}_p*.csv; do
                        if [ -f "$TMP_F" ]; then
                            FILE_MTIME=$(stat -c %Y "$TMP_F" 2>/dev/null || echo "$NOW_SEC")
                            IDLE_SEC=$(( NOW_SEC - FILE_MTIME ))
                            if [ "$IDLE_SEC" -ge 600 ]; then
                                MUST_RESTART=true
                                INACTIVE_PORT=$(basename "$TMP_F" | sed -E 's/.*_(p[0-9]+)_b[0-9]+\.csv/\1/')
                                avis_telegram "⏳ [Thread Inactivity] Matchup ${MATCHUP_TAG} port ${INACTIVE_PORT} idle for $(( IDLE_SEC / 60 ))m (>10m limit). Saving progress and restarting batch..."
                                break
                            fi
                        fi
                    done

                    # ── Standard 20-Minute Progress Telemetry & General Stall Check ──
                    if [ "$TELEM_COUNTER" -ge 20 ]; then
                        TELEM_COUNTER=0
                        PCT=$(awk -v done="$TOTAL_DONE" -v target="$TARGET_N" 'BEGIN { printf "%.1f", (done/target)*100 }')
                        echo "[$(date '+%H:%M')] Checking matchup ${MATCHUP_TAG}: ${TOTAL_DONE}/${TARGET_N} (${PCT}%)"
                        avis_telegram "📊 [20m Progress] ${MATCHUP_TAG}: ~${TOTAL_DONE}/${TARGET_N} games (${PCT}%) | $(date '+%H:%M')"

                        if [ "$IS_MCTS" = false ] && [ "$MATCHUP_TAG" = "$LAST_MATCHUP" ]; then
                            REMAINING=$(( TARGET_N - TOTAL_DONE ))
                            MIN_ADVANCE=$(( TARGET_N / 10 ))
                            [ $MIN_ADVANCE -gt $REMAINING ] && MIN_ADVANCE=$REMAINING
                            [ $MIN_ADVANCE -lt 50 ] && MIN_ADVANCE=50

                            DIFF=$(( TOTAL_DONE - LAST_ROWS ))
                            if [ $DIFF -lt $MIN_ADVANCE ] && [ $REMAINING -gt 0 ]; then
                                MUST_RESTART=true
                                avis_telegram "⚠️  Stuck detected for ${MATCHUP_TAG}! Only +${DIFF} games in 20m (${NUM_FILES} active thread/s left, min required ${MIN_ADVANCE}). Saving progress and restarting batch..."
                            fi
                        fi
                    fi

                    # ── Execute Auto-Merge & Kill Process on Restart Trigger ──
                    if [ "$MUST_RESTART" = true ]; then
                        uv run python -c "
import glob, os, pandas as pd
matchup = '$MATCHUP_TAG'
out_dir = '$OUT_DIR'
files = glob.glob(f'{out_dir}/_tmp_{matchup}_p*.csv')
if files:
    dfs = []
    for f in files:
        if os.path.exists(f) and os.path.getsize(f) > 0:
            try:
                dfs.append(pd.read_csv(f))
            except Exception:
                pass
    if dfs:
        merged = pd.concat(dfs, ignore_index=True)
        if 'heuristic' in merged.columns and 'opponent' in merged.columns and len(merged) > 0:
            ag = merged['heuristic'].iloc[0]
            op = merged['opponent'].iloc[0]
            out_csv = f'{out_dir}/{ag}_vs_{op}.csv'
        else:
            out_csv = f'{out_dir}/{matchup}.csv'

        if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
            try:
                existing_df = pd.read_csv(out_csv)
                merged = pd.concat([existing_df, merged], ignore_index=True)
            except Exception:
                pass

        if 'battle_id' in merged.columns:
            merged.drop_duplicates(subset=['battle_id'], inplace=True)
        else:
            merged.drop_duplicates(inplace=True)

        merged.to_csv(out_csv, index=False)
        print(f'Auto-merged stuck progress into {out_csv}. Total rows: {len(merged)}')
        for f in files:
            try:
                os.remove(f)
            except Exception:
                pass
"
                        pkill -f "benchmark.py" || true
                        pkill -f "pokemon-showdown" || true
                        pkill -f "worker.py" || true
                        for PORT in $(seq 8000 8040); do
                            fuser -k "${PORT}/tcp" 2>/dev/null || true
                        done
                        STALL_COUNTER=0
                        LAST_ROWS=0
                        LAST_MATCHUP=""
                    else
                        LAST_ROWS=$TOTAL_DONE
                        LAST_MATCHUP=$MATCHUP_TAG
                    fi

                else
                    if [ "$TELEM_COUNTER" -ge 20 ]; then
                        TELEM_COUNTER=0
                        echo "[$(date '+%H:%M')] No active tmp files found."
                        avis_telegram "📊 [20m Progress] Idle / No active batch files (matchup complete or transitioning) | $(date '+%H:%M')"
                    fi
                    LAST_ROWS=0
                    LAST_MATCHUP=""
                    STALL_COUNTER=0
                fi
            fi
        done
    ) > "$OUT_DIR/monitor.log" 2>&1 &
    MONITOR_PID=$!
}

# ── Cleanup & Pre-flight Port Health Check ─────────────────────────────────────
cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null || true
    pkill -f "worker.py" 2>/dev/null || true
    
    # Pre-flight check & force kill on ports 8000..8040
    for PORT in $(seq 8000 8040); do
        # Kill process holding port if any
        fuser -k -9 "${PORT}/tcp" 2>/dev/null || true
    done
    sleep 3
    
    # Verify ports are clear; retry fuser if any port remains occupied
    for PORT in $(seq 8000 8040); do
        if nc -z -w 1 127.0.0.1 "$PORT" 2>/dev/null; then
            fuser -k -9 "${PORT}/tcp" 2>/dev/null || true
        fi
    done
    sync
}

# ── Auto-merge leftover temporary files on interrupt ──────────────────────────
merge_active_tmp_files() {
    if [ -d "$OUT_DIR" ]; then
        ACTIVE_FILE=$(ls -t "$OUT_DIR"/_tmp_*.csv 2>/dev/null | head -n 1 || true)
        if [ -n "$ACTIVE_FILE" ]; then
            MATCHUP_TAG=$(basename "$ACTIVE_FILE" | sed -E 's/_tmp_(.*)_p[0-9]+_b[0-9]+\.csv/\1/')
            echo "💾 Auto-merging active progress for ${MATCHUP_TAG} before exit..."
            uv run python -c "
import glob, os, pandas as pd
matchup = '$MATCHUP_TAG'
out_dir = '$OUT_DIR'
files = glob.glob(f'{out_dir}/_tmp_{matchup}_p*.csv')
if files:
    dfs = []
    for f in files:
        if os.path.exists(f) and os.path.getsize(f) > 0:
            try:
                dfs.append(pd.read_csv(f))
            except Exception:
                pass
    if dfs:
        merged = pd.concat(dfs, ignore_index=True)
        if 'heuristic' in merged.columns and 'opponent' in merged.columns and len(merged) > 0:
            ag = merged['heuristic'].iloc[0]
            op = merged['opponent'].iloc[0]
            out_csv = f'{out_dir}/{ag}_vs_{op}.csv'
        else:
            out_csv = f'{out_dir}/{matchup}.csv'

        if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
            try:
                existing_df = pd.read_csv(out_csv)
                merged = pd.concat([existing_df, merged], ignore_index=True)
            except Exception:
                pass

        if 'battle_id' in merged.columns:
            merged.drop_duplicates(subset=['battle_id'], inplace=True)
        else:
            merged.drop_duplicates(inplace=True)

        merged.to_csv(out_csv, index=False)
        print(f'✅ Successfully saved {len(merged)} total games to {out_csv}')
        for f in files:
            try:
                os.remove(f)
            except Exception:
                pass
" 2>/dev/null || true
        fi
    fi
}

cleanup_all() {
    echo "🛑 SIGINT/SIGTERM caught! Merging active files and terminating processes..."
    merge_active_tmp_files
    [ -n "$MONITOR_PID" ] && kill -9 "$MONITOR_PID" 2>/dev/null || true
    pkill -9 -f "benchmark.py" 2>/dev/null || true
    pkill -9 -f "worker.py" 2>/dev/null || true
    cleanup
}

# ── On kill/interrupt ──────────────────────────────────────────────────────────
trap 'cleanup_all; avis_telegram "🛑 KILLED: Paradigm evaluation benchmark was interrupted. Re-run to resume."; exit 130' SIGTERM SIGINT SIGHUP

# ── Count total matchups ───────────────────────────────────────────────────────
N_ALL=$(echo $ALL_AGENTS | wc -w)
N_NEW=$(echo $NEW_AGENTS | wc -w)
TOTAL_MATCHUPS=$(( N_NEW * N_ALL ))

echo "════════════════════════════════════════════════════════"
echo " Final Paradigm Comparison Evaluation (10k games)"
echo " Evaluated Agents : ${NEW_AGENTS}"
echo " Opponent Gauntlet: ${N_ALL} agents"
echo " Target Matchups  : ${TOTAL_MATCHUPS} matchups × ${N_BATTLES} games"
echo " Output Location  : ${OUT_DIR}/"
echo "════════════════════════════════════════════════════════"

TOTAL_START=$(date +%s)
avis_telegram "🚀 Starting final comparative evaluation: ${N_NEW} agents × ${N_ALL} opponents = ${TOTAL_MATCHUPS} matchups | $(date '+%H:%M')"

cleanup  # clean up any leftover processes
start_telegram_monitor  # start background 15-minute progress monitor

# ── Main loop ──────────────────────────────────────────────────────────────────
AGENT_IDX=0
for AGENT in $NEW_AGENTS; do
    START_AGENT=$(date +%s)
    AGENT_IDX=$(( AGENT_IDX + 1 ))
    avis_telegram "⚔️  [${AGENT_IDX}/${N_NEW}] Starting ${AGENT} evaluation vs gauntlet | $(date '+%H:%M')"

    for OPPONENT in $ALL_AGENTS; do
        ATTEMPT=0
        SUCCESS=false

        while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
            ATTEMPT=$(( ATTEMPT + 1 ))

            if [ $ATTEMPT -gt 1 ]; then
                avis_telegram "🔄 [${AGENT} vs ${OPPONENT}] Retry ${ATTEMPT}/${MAX_RETRIES} | $(date '+%H:%M')"
                cleanup
                sleep 10
            fi

            # Hardware Tuning for Ryzen 7 5700X3D (8C/16T) & 30GB RAM:
            # - MCTS (v18..v20): 1,000 battles/matchup, 10 ports / 20 concurrency.
            # - Heavy Minimax (v15..v17): 10,000 battles, 8 ports / 15 concurrency (prevents CPU cache/RAM contention).
            # - Fast & Baselines (v1..v14, v21, v22, baselines): 10,000 battles, 8 ports / 25 concurrency.
            if [[ "$AGENT" =~ ^v(18|19|20)$ ]] || [[ "$OPPONENT" =~ ^v(18|19|20)$ ]]; then
                CURRENT_N=1000
                CURRENT_PORTS=10
                CURRENT_CONCURRENCY=20
            elif [[ "$AGENT" =~ ^v(15|16|17)$ ]] || [[ "$OPPONENT" =~ ^v(15|16|17)$ ]]; then
                CURRENT_N=${N_BATTLES:-10000}
                CURRENT_PORTS=8
                CURRENT_CONCURRENCY=15
            else
                CURRENT_N=${N_BATTLES:-10000}
                CURRENT_PORTS=${PORTS:-8}
                CURRENT_CONCURRENCY=${CONCURRENCY:-25}
            fi

            # Instant Skip Check: Skip in 0.001s if matchup CSV is already completed on disk!
            OUT_CSV="${OUT_DIR}/${AGENT}_vs_${OPPONENT}.csv"
            if [ -f "$OUT_CSV" ]; then
                EXISTING_ROWS=$(wc -l < "$OUT_CSV" 2>/dev/null || echo 0)
                EXISTING_GAMES=$(( EXISTING_ROWS > 0 ? EXISTING_ROWS - 1 : 0 ))
                if [ "$EXISTING_GAMES" -ge "$CURRENT_N" ]; then
                    echo "⏩ Skipping ${AGENT} vs ${OPPONENT} (${EXISTING_GAMES}/${CURRENT_N} games already done)"
                    SUCCESS=true
                    break
                fi
            fi

            set +e
            uv run python src/p00_core/engine/benchmark.py \
                $CURRENT_N \
                --agents "$AGENT" \
                --opponents "$OPPONENT" \
                --ports $CURRENT_PORTS \
                --concurrency $CURRENT_CONCURRENCY \
                --battle-format gen9randombattle \
                --out "$OUT_DIR" \
                --restart-every $RESTART_EVERY
            EXIT_CODE=$?
            set -e

            if [ $EXIT_CODE -eq 0 ]; then
                SUCCESS=true
            elif [ $EXIT_CODE -eq 130 ] || [ $EXIT_CODE -eq 137 ] || [ $EXIT_CODE -eq 2 ]; then
                echo "🛑 SIGINT/Ctrl+C detected during python execution. Exiting loop."
                cleanup_all
                exit 130
            else
                avis_telegram "⚠️  [${AGENT} vs ${OPPONENT}] FAIL attempt ${ATTEMPT}/${MAX_RETRIES} (exit ${EXIT_CODE})"
                cleanup
            fi
        done
    done

    END_AGENT=$(date +%s)
    AGENT_MIN=$(( (END_AGENT - START_AGENT) / 60 ))
    AGENT_HOURS=$(( AGENT_MIN / 60 ))
    AGENT_REM=$(( AGENT_MIN % 60 ))

    avis_telegram "✅ [${AGENT_IDX}/${N_NEW}] ${AGENT} DONE in ${AGENT_HOURS}h${AGENT_REM}m | $(date '+%H:%M')"
    cleanup  # clean between agents
done

# ── Final summary ──────────────────────────────────────────────────────────────
TOTAL_END=$(date +%s)
TOTAL_HOURS=$(( (TOTAL_END - TOTAL_START) / 3600 ))
TOTAL_MIN=$(( ((TOTAL_END - TOTAL_START) % 3600) / 60 ))

echo ""
echo "════════════════════════════════════════════════════════"
echo " PARADIGM TOURNAMENT COMPLETED in ${TOTAL_HOURS}h${TOTAL_MIN}m"
echo " Results stored in: ${OUT_DIR}/"
echo "════════════════════════════════════════════════════════"

avis_telegram "🏁 PARADIGM COMPARISON COMPLETED in ${TOTAL_HOURS}h${TOTAL_MIN}m. Final telemetry saved to ${OUT_DIR}/ | $(date '+%H:%M')"
