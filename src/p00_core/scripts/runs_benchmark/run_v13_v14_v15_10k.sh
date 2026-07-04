#!/bin/bash
# run_v13_v14_v15_10k.sh — Complete all missing v13, v14, v15 matchups in all_10k
#
# Runs each new agent against ALL standard opponents (v1-v14 + baselines).
# Uses benchmark.py resume logic: already-finished matchups are skipped instantly.
#
# USAGE (in tmux):
#   tmux new -s benchmark_new
#   bash src/p00_core/scripts/runs_benchmark/run_v13_v14_v15_10k.sh 2>&1 | tee benchmark_new.log
#
# To also monitor safety (CPU/RAM/NVMe temps + process watchdog), in another pane:
#   bash src/p00_core/scripts/seguretat_tfm.sh

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
            -d text="$1" > /dev/null
    else
        echo "[NOTIFY] $1"
    fi
}

# ── Configuration ──────────────────────────────────────────────────────────────
# All known agents (opponents for round-robin)
ALL_AGENTS="v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 random max_power abyssal one_step safe_one_step simple_heuristic"

# New agents to benchmark (as primary agents)
NEW_AGENTS="v13 v14 v15"

N_BATTLES=10000
PORTS=8
CONCURRENCY=25
OUT_DIR="data/benchmarks/all_10k/gen9randombattle"
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
trap 'cleanup; avis_telegram "🛑 KILLED: v13/v14/v15 benchmark was interrupted. Re-run to resume from where it stopped."; exit 1' SIGTERM SIGINT SIGHUP

# ── Count total matchups ───────────────────────────────────────────────────────
N_ALL=$(echo $ALL_AGENTS | wc -w)
N_NEW=$(echo $NEW_AGENTS | wc -w)
TOTAL_MATCHUPS=$(( N_NEW * N_ALL ))

echo "════════════════════════════════════════════════════════"
echo " v13 / v14 / v15 — All-10k Benchmark"
echo " New agents : ${NEW_AGENTS}"
echo " Opponents  : ${N_ALL} agents"
echo " Target     : ${TOTAL_MATCHUPS} matchups × ${N_BATTLES} games"
echo " Output     : ${OUT_DIR}/"
echo "════════════════════════════════════════════════════════"

TOTAL_START=$(date +%s)
avis_telegram "🚀 Starting v13/v14/v15 10k benchmark: ${N_NEW} agents × ${N_ALL} opponents = ${TOTAL_MATCHUPS} matchups | $(date '+%H:%M')"

cleanup  # clean up any leftover processes

# ── Main loop ──────────────────────────────────────────────────────────────────
AGENT_IDX=0
for AGENT in $NEW_AGENTS; do
    AGENT_IDX=$(( AGENT_IDX + 1 ))
    ATTEMPT=0
    SUCCESS=false

    START_AGENT=$(date +%s)
    avis_telegram "⚔️  [${AGENT_IDX}/${N_NEW}] Starting ${AGENT} vs all ${N_ALL} opponents | $(date '+%H:%M')"

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
echo " ALL DONE in ${TOTAL_HOURS}h${TOTAL_MIN}m"
echo " Results in: ${OUT_DIR}/"
echo "════════════════════════════════════════════════════════"

avis_telegram "🏁 ALL DONE: v13/v14/v15 benchmark complete in ${TOTAL_HOURS}h${TOTAL_MIN}m. Results in ${OUT_DIR}/ | $(date '+%H:%M')"
