#!/bin/bash
# run_all_10k.sh — FULL round-robin tournament: all 18 agents × gen1-9 × 10k games
#
# CRASH SAFETY: benchmark.py auto-resumes — running this script again after a
# crash will skip already-finished matchups and continue from where it left off.
# NOTHING IS LOST on crash or kill.
#
# AGENTS: v1-v12 (internal heuristics) + random, max_power, abyssal,
#         one_step, safe_one_step, simple_heuristic (baselines) = 18 total
# MATCHUPS: 18×18 = 324 per gen × 9 gens = 2916 total
# ESTIMATED TIME: ~65 hours (~2.7 days) at 8 ports / 20 concurrency
#
# USAGE:
#   chmod +x src/p05_scripts/run_all_10k.sh
#   tmux new -s benchmark
#   bash src/p05_scripts/run_all_10k.sh 2>&1 | tee benchmark_log.txt

# ── Telegram notification (defined in ~/.bashrc; safe no-op if missing) ──────
if grep -q 'avis_telegram()' ~/.bashrc 2>/dev/null; then
    eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"
else
    avis_telegram() { echo "[NOTIFY] $1"; }
fi

# ── Configuration ─────────────────────────────────────────────────────────────
GENS="gen4randombattle gen5randombattle gen6randombattle gen7randombattle gen8randombattle gen9randombattle"
AGENTS="v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 random max_power abyssal one_step safe_one_step simple_heuristic"
N_BATTLES=10000
PORTS=8
CONCURRENCY=20
OUT_BASE="data/1_vs_1/benchmarks_all_10k"
MAX_RETRIES=3
RESTART_EVERY=20    # restart Showdown servers every N matchups to prevent memory leaks

# ── Cleanup helper ────────────────────────────────────────────────────────────
cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null
    pkill -f "worker.py" 2>/dev/null
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "${PORT}/tcp" 2>/dev/null
    done
    pkill -f "s01_singles/evaluation/engine" 2>/dev/null
    sleep 5
    sync
}

# ── On kill/interrupt: clean up and notify ────────────────────────────────────
trap 'cleanup; avis_telegram "KILLED: full 10k tournament was terminated. Re-run to resume."; exit 1' SIGTERM SIGINT SIGHUP

# ── Count total agents for progress messages ──────────────────────────────────
N_AGENTS=$(echo $AGENTS | wc -w)
TOTAL_MATCHUPS_PER_GEN=$(( N_AGENTS * N_AGENTS ))

TOTAL_START=$(date +%s)
avis_telegram "Starting FULL 10k tournament: ${N_AGENTS} agents × 9 gens × ${N_BATTLES} games (~2.7 days) | $(date '+%H:%M')"

cleanup  # clean up any leftover processes from previous runs

# ─────────────────────────────────────────────────────────────────────────────
# Main loop: per generation, per agent
# Each agent runs all its matchups as a single benchmark.py call (efficient).
# On crash, benchmark.py's resume logic means re-running skips finished games.
# ─────────────────────────────────────────────────────────────────────────────
for GEN in $GENS; do
    avis_telegram "[${GEN}] Starting (${TOTAL_MATCHUPS_PER_GEN} matchups)"
    START_GEN=$(date +%s)
    GEN_AGENTS_DONE=0
    GEN_AGENTS_FAIL=0

    for AGENT in $AGENTS; do
        ATTEMPT=0
        SUCCESS=false

        while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
            ATTEMPT=$(( ATTEMPT + 1 ))

            if [ $ATTEMPT -gt 1 ]; then
                avis_telegram "[${GEN}] ${AGENT} retry ${ATTEMPT}/${MAX_RETRIES}"
                cleanup
                sleep 10
            fi

            START_AGENT=$(date +%s)

            uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py \
                $N_BATTLES \
                --agents "$AGENT" \
                --opponents $AGENTS \
                --ports $PORTS \
                --concurrency $CONCURRENCY \
                --battle-format "$GEN" \
                --out "${OUT_BASE}/${GEN}" \
                --restart-every $RESTART_EVERY
            EXIT_CODE=$?

            END_AGENT=$(date +%s)
            AGENT_MIN=$(( (END_AGENT - START_AGENT) / 60 ))

            if [ $EXIT_CODE -eq 0 ]; then
                SUCCESS=true
                GEN_AGENTS_DONE=$(( GEN_AGENTS_DONE + 1 ))
                avis_telegram "[${GEN}] ${AGENT} done (${AGENT_MIN}m) [${GEN_AGENTS_DONE}/${N_AGENTS}]"
            else
                avis_telegram "[${GEN}] ${AGENT} FAIL attempt ${ATTEMPT} (exit ${EXIT_CODE}, ${AGENT_MIN}m)"
                cleanup
            fi
        done

        if [ "$SUCCESS" = false ]; then
            GEN_AGENTS_FAIL=$(( GEN_AGENTS_FAIL + 1 ))
            avis_telegram "[${GEN}] ${AGENT} ABORT after ${MAX_RETRIES} attempts — continuing to next agent"
        fi
    done

    END_GEN=$(date +%s)
    GEN_HOURS=$(( (END_GEN - START_GEN) / 3600 ))
    GEN_MIN=$(( ((END_GEN - START_GEN) % 3600) / 60 ))
    avis_telegram "GEN DONE: ${GEN} in ${GEN_HOURS}h${GEN_MIN}m (${GEN_AGENTS_DONE} ok, ${GEN_AGENTS_FAIL} failed)"

    cleanup  # clean between gens
done

TOTAL_END=$(date +%s)
TOTAL_HOURS=$(( (TOTAL_END - TOTAL_START) / 3600 ))
TOTAL_MIN=$(( ((TOTAL_END - TOTAL_START) % 3600) / 60 ))
avis_telegram "ALL DONE: Full 10k tournament finished in ${TOTAL_HOURS}h${TOTAL_MIN}m. Results in ${OUT_BASE}/ | $(date '+%H:%M')"
