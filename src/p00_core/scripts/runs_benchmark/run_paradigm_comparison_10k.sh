#!/bin/bash
# run_paradigm_comparison_10k.sh — Runs the complete 10k game comparative tournament
# among all core thesis paradigms: Championship Heuristic, Minimax, MCTS, and Imitation.
#
# MATCHUP MATRIX:
#   Primary Agents (NEW_AGENTS) : v14, v15_minimax, v16_minimax, v17_minimax_hybrid, v18_mcts, v19_mcts, v20_mcts_hybrid, v21_xgboost
#   Gauntlet (ALL_AGENTS)       : v1, v8, v12, v14, v15_minimax, v16_minimax, v17_minimax_hybrid, v18_mcts, v19_mcts, v20_mcts_hybrid, v21_xgboost, random, max_power, abyssal
#
# TELEMETRY:
#   Saved to data/benchmarks/gen9_paradigm_eval/ containing advanced columns:
#   - search_diff_us / search_diff_opp
#   - xgb_switches_us / xgb_switches_opp
#   - xgb_stays_us / xgb_stays_opp
#   - ko_guards_us / ko_guards_opp
#   - loop_guards_us / loop_guards_opp
#
# USAGE (in tmux):
#   tmux new -s paradigm_eval
#   bash src/p00_core/scripts/runs_benchmark/run_paradigm_comparison_10k.sh 2>&1 | tee paradigm_eval.log
#

set -euo pipefail

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
ALL_AGENTS=${ALL_AGENTS:-"v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15_minimax v16_minimax v17_minimax_hybrid v18_mcts v19_mcts v20_mcts_hybrid v21_xgboost random max_power abyssal one_step safe_one_step simple_heuristic"}

# Main agents under evaluation
# Default is all agents so every pair (A, B) runs both A vs B and B vs A (20k games total per pair):
NEW_AGENTS=${NEW_AGENTS:-"v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15_minimax v16_minimax v17_minimax_hybrid v18_mcts v19_mcts v20_mcts_hybrid v21_xgboost random max_power abyssal one_step safe_one_step simple_heuristic"}

N_BATTLES=${N_BATTLES:-10000}
PORTS=${PORTS:-8}
CONCURRENCY=${CONCURRENCY:-25}
OUT_DIR=${OUT_DIR:-"data/benchmarks/all_10k/gen9randombattle"}
RESTART_EVERY=20    # restart Showdown servers every N matchups to prevent memory bloat
MAX_RETRIES=3

# ── Cleanup helper ─────────────────────────────────────────────────────────────
cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null || true
    pkill -f "worker.py" 2>/dev/null || true
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "${PORT}/tcp" 2>/dev/null || true
    done
    sleep 3
    sync
}

# ── On kill/interrupt ──────────────────────────────────────────────────────────
trap 'cleanup; avis_telegram "🛑 KILLED: Paradigm evaluation benchmark was interrupted. Re-run to resume."; exit 1' SIGTERM SIGINT SIGHUP

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

# ── Main loop ──────────────────────────────────────────────────────────────────
AGENT_IDX=0
for AGENT in $NEW_AGENTS; do
    AGENT_IDX=$(( AGENT_IDX + 1 ))
    ATTEMPT=0
    SUCCESS=false

    START_AGENT=$(date +%s)
    avis_telegram "⚔️  [${AGENT_IDX}/${N_NEW}] Starting ${AGENT} evaluation vs gauntlet | $(date '+%H:%M')"

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
        fi
    done

    END_AGENT=$(date +%s)
    AGENT_MIN=$(( (END_AGENT - START_AGENT) / 60 ))
    AGENT_HOURS=$(( AGENT_MIN / 60 ))
    AGENT_REM=$(( AGENT_MIN % 60 ))

    if [ "$SUCCESS" = true ]; then
        avis_telegram "✅ [${AGENT_IDX}/${N_NEW}] ${AGENT} DONE in ${AGENT_HOURS}h${AGENT_REM}m | $(date '+%H:%M')"
    else
        avis_telegram "❌ [${AGENT_IDX}/${N_NEW}] ${AGENT} ABORTED after ${MAX_RETRIES} retries — continuing"
    fi

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
