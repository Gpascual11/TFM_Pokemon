#!/bin/bash
# run_all_gens.sh — Full benchmark across gen1-gen9 with Telegram notifications
# Fire-and-forget: retries on failure, cleans RAM/processes between attempts.
# Notifies per-agent (when all matchups for one agent finish) and per-gen.

# Load avis_telegram from bashrc (token stays private there)
eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"

GENS="gen1randombattle gen2randombattle gen3randombattle gen4randombattle gen5randombattle gen6randombattle gen7randombattle gen8randombattle gen9randombattle"
AGENTS="v1 v2 v3 v4 v5 v6 v7 v8 random max_power abyssal one_step safe_one_step simple_heuristic"
N_BATTLES=10000
PORTS=8
CONCURRENCY=30
OUT_BASE="data/1_vs_1/benchmarks_10k"
MAX_RETRIES=3
MAX_TIME_PER_MATCHUP=1800  # 30 min threshold for slow alert

cleanup() {
    # Kill all Showdown server processes
    pkill -f "pokemon-showdown" 2>/dev/null
    # Kill any zombie worker.py subprocesses
    pkill -f "worker.py" 2>/dev/null
    # Kill any lingering node processes on our port range
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "$PORT/tcp" 2>/dev/null
    done
    # Force Python garbage collection by killing orphan uv/python children
    pkill -f "s01_singles/evaluation/engine" 2>/dev/null
    # Wait for OS to release ports and reclaim memory
    sleep 5
    # Drop filesystem caches (helps on long runs; needs sudo or skip silently)
    sync
    echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1 || true
}

# Trap: if the script itself is killed, clean up
trap 'cleanup; avis_telegram "KILLED: benchmark script was terminated"; exit 1' SIGTERM SIGINT SIGHUP

avis_telegram "Starting full benchmark: 10k games x 9 gens ($(date '+%H:%M'))"

# Initial cleanup of any leftover processes from previous runs
cleanup

for GEN in $GENS; do
    avis_telegram "[$GEN] Starting"
    START_GEN=$(date +%s)
    GEN_AGENTS_DONE=0
    GEN_AGENTS_FAIL=0

    for AGENT in $AGENTS; do
        ATTEMPT=0
        SUCCESS=false

        while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
            ATTEMPT=$((ATTEMPT + 1))

            if [ $ATTEMPT -gt 1 ]; then
                avis_telegram "[$GEN] $AGENT retry $ATTEMPT/$MAX_RETRIES"
                cleanup
                sleep 10
            fi

            START_AGENT=$(date +%s)

            uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py $N_BATTLES \
                --agents "$AGENT" \
                --ports $PORTS \
                --concurrency $CONCURRENCY \
                --battle-format "$GEN" \
                --out "$OUT_BASE/$GEN" \
                --restart-every 3
            EXIT_CODE=$?

            END_AGENT=$(date +%s)
            AGENT_DURATION=$(( END_AGENT - START_AGENT ))
            AGENT_MIN=$(( AGENT_DURATION / 60 ))

            if [ $EXIT_CODE -eq 0 ]; then
                SUCCESS=true
                GEN_AGENTS_DONE=$((GEN_AGENTS_DONE + 1))
                avis_telegram "[$GEN] $AGENT done (${AGENT_MIN}m) [$GEN_AGENTS_DONE/14]"
            else
                avis_telegram "[$GEN] $AGENT FAIL attempt $ATTEMPT (exit $EXIT_CODE, ${AGENT_MIN}m)"
                cleanup
            fi
        done

        if [ "$SUCCESS" = false ]; then
            GEN_AGENTS_FAIL=$((GEN_AGENTS_FAIL + 1))
            avis_telegram "[$GEN] $AGENT ABORT after $MAX_RETRIES attempts"
        fi
    done

    END_GEN=$(date +%s)
    GEN_DURATION=$(( END_GEN - START_GEN ))
    GEN_HOURS=$(( GEN_DURATION / 3600 ))
    GEN_MIN=$(( (GEN_DURATION % 3600) / 60 ))

    avis_telegram "GEN DONE: $GEN in ${GEN_HOURS}h${GEN_MIN}m (${GEN_AGENTS_DONE} ok, ${GEN_AGENTS_FAIL} failed)"

    # Clean between gens
    cleanup
done

avis_telegram "ALL DONE. Results in $OUT_BASE/ ($(date '+%H:%M'))"
