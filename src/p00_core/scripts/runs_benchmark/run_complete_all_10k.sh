#!/bin/bash
# run_complete_all_10k.sh — Complete ALL missing matchups across ALL gens in all_10k/
#
# Full round-robin: 21 agents × 20 opponents × 9 gens = 3780 matchups total.
# benchmark.py resume logic skips already-finished matchups instantly.
# ~114 missing per gen (v13/v14/v15 rows) + any partial/failed ones.
#
# AGENTS: v1-v15, random, max_power, abyssal, one_step, safe_one_step, simple_heuristic
#
# USAGE (in tmux):
#   tmux new -s bench_complete
#   cd ~/Documents/MUDS/TFM_Pokemon
#   bash src/p00_core/scripts/runs_benchmark/run_complete_all_10k.sh 2>&1 | tee bench_complete.log
#
# Safety monitor (second tmux pane, Ctrl+B %):
#   bash src/p00_core/scripts/seguretat_tfm.sh

set -euo pipefail

# ── Load credentials from .env ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.venv/bin/activate"
else
    echo "⚠️  No .venv found at $ROOT_DIR/.venv — using current Python environment."
fi

if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
else
    echo "⚠️  No .env found at $ENV_FILE — Telegram notifications disabled."
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
ALL_AGENTS="v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 random max_power abyssal one_step safe_one_step simple_heuristic"

# All 9 gens to complete
GENS="gen1randombattle gen2randombattle gen3randombattle gen4randombattle gen5randombattle gen6randombattle gen7randombattle gen8randombattle gen9randombattle"

N_BATTLES=10000
PORTS=8
CONCURRENCY=25
OUT_BASE="data/benchmarks/all_10k"
RESTART_EVERY=20
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

trap 'cleanup; avis_telegram "🛑 INTERRUPTED: complete_all_10k. Re-run to resume — no progress lost."; exit 1' SIGTERM SIGINT SIGHUP

# ── Stats ─────────────────────────────────────────────────────────────────────
N_AGENTS=$(echo $ALL_AGENTS | wc -w)
N_GENS=$(echo $GENS | wc -w)
TOTAL_MATCHUPS=$(( N_AGENTS * (N_AGENTS - 1) * N_GENS ))

echo "════════════════════════════════════════════════════════════════"
echo " Complete All-10k Benchmark — Fill All Missing Matchups"
echo " Agents    : ${N_AGENTS} (v1-v15 + 6 baselines)"
echo " Gens      : ${N_GENS}"
echo " Total     : ${TOTAL_MATCHUPS} matchups (already-done skipped instantly)"
echo " Output    : ${OUT_BASE}/<gen>/"
echo "════════════════════════════════════════════════════════════════"
echo ""

TOTAL_START=$(date +%s)
avis_telegram "🚀 complete_all_10k started: ${N_AGENTS} agents × ${N_GENS} gens = ${TOTAL_MATCHUPS} matchups (skipping done ones) | $(date '+%H:%M')"

cleanup

# ── Main loop ──────────────────────────────────────────────────────────────────
GEN_IDX=0
for GEN in $GENS; do
    GEN_IDX=$(( GEN_IDX + 1 ))
    GEN_START=$(date +%s)
    GEN_AGENTS_DONE=0
    GEN_AGENTS_FAIL=0

    avis_telegram "📂 [${GEN_IDX}/${N_GENS}] Starting ${GEN} | $(date '+%H:%M')"
    echo ""
    echo "══ GEN ${GEN_IDX}/${N_GENS}: $GEN ══"

    AGENT_IDX=0
    for AGENT in $ALL_AGENTS; do
        AGENT_IDX=$(( AGENT_IDX + 1 ))
        ATTEMPT=0
        SUCCESS=false

        while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
            ATTEMPT=$(( ATTEMPT + 1 ))

            if [ $ATTEMPT -gt 1 ]; then
                avis_telegram "🔄 [${GEN}] ${AGENT} retry ${ATTEMPT}/${MAX_RETRIES}"
                cleanup
                sleep 10
            fi

            # Periodic restart every RESTART_EVERY agents to prevent memory bloat
            if [ $(( (AGENT_IDX - 1) % RESTART_EVERY )) -eq 0 ] && [ $ATTEMPT -eq 1 ]; then
                cleanup
                sleep 5
            fi

            python src/p00_core/engine/benchmark.py \
                $N_BATTLES \
                --agents "$AGENT" \
                --opponents $ALL_AGENTS \
                --ports $PORTS \
                --concurrency $CONCURRENCY \
                --battle-format "$GEN" \
                --out "${OUT_BASE}/${GEN}" \
                --restart-every $RESTART_EVERY
            EXIT_CODE=$?

            if [ $EXIT_CODE -eq 0 ]; then
                SUCCESS=true
                GEN_AGENTS_DONE=$(( GEN_AGENTS_DONE + 1 ))
            else
                avis_telegram "⚠️  [${GEN}] ${AGENT} FAIL attempt ${ATTEMPT} (exit ${EXIT_CODE})"
                cleanup
            fi
        done

        if [ "$SUCCESS" = false ]; then
            GEN_AGENTS_FAIL=$(( GEN_AGENTS_FAIL + 1 ))
            avis_telegram "❌ [${GEN}] ${AGENT} ABORTED after ${MAX_RETRIES} retries"
        fi
    done

    GEN_END=$(date +%s)
    GEN_HOURS=$(( (GEN_END - GEN_START) / 3600 ))
    GEN_MIN=$(( ((GEN_END - GEN_START) % 3600) / 60 ))
    avis_telegram "✅ [${GEN_IDX}/${N_GENS}] ${GEN} DONE in ${GEN_HOURS}h${GEN_MIN}m (${GEN_AGENTS_DONE} ok, ${GEN_AGENTS_FAIL} failed) | $(date '+%H:%M')"

    cleanup
done

# ── Final summary ──────────────────────────────────────────────────────────────
TOTAL_END=$(date +%s)
TOTAL_HOURS=$(( (TOTAL_END - TOTAL_START) / 3600 ))
TOTAL_MIN=$(( ((TOTAL_END - TOTAL_START) % 3600) / 60 ))

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " ALL DONE in ${TOTAL_HOURS}h${TOTAL_MIN}m"
echo " Results in: ${OUT_BASE}/"
echo "════════════════════════════════════════════════════════════════"

avis_telegram "🏁 ALL DONE: complete_all_10k finished in ${TOTAL_HOURS}h${TOTAL_MIN}m. All 9 gens × 21 agents complete. | $(date '+%H:%M')"
