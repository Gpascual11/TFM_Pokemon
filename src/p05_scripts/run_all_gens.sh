#!/bin/bash
# run_all_gens.sh — Full benchmark across gen1-gen9 with Telegram notifications
# Fire-and-forget: retries on failure, cleans RAM/processes between attempts.

# Load avis_telegram from bashrc (token stays private there)
eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"

GENS="gen1randombattle gen2randombattle gen3randombattle gen4randombattle gen5randombattle gen6randombattle gen7randombattle gen8randombattle gen9randombattle"
N_BATTLES=10000
PORTS=4
CONCURRENCY=10
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
    ATTEMPT=0
    SUCCESS=false

    while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
        ATTEMPT=$((ATTEMPT + 1))

        if [ $ATTEMPT -eq 1 ]; then
            avis_telegram "[$GEN] Starting"
        else
            avis_telegram "[$GEN] Retry $ATTEMPT/$MAX_RETRIES"
        fi

        START_GEN=$(date +%s)

        # Clean everything before each attempt
        cleanup

        uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py $N_BATTLES \
            --ports $PORTS \
            --concurrency $CONCURRENCY \
            --battle-format "$GEN" \
            --out "$OUT_BASE/$GEN" \
            --restart-every 3
        EXIT_CODE=$?

        END_GEN=$(date +%s)
        DURATION=$(( END_GEN - START_GEN ))
        DURATION_MIN=$(( DURATION / 60 ))

        if [ $EXIT_CODE -eq 0 ]; then
            SUCCESS=true
            N_FILES=$(find "$OUT_BASE/$GEN" -name "*.csv" ! -name "_tmp_*" ! -name "matchup_*" | wc -l)
            AVG_SEC=0
            [ "$N_FILES" -gt 0 ] && AVG_SEC=$(( DURATION / N_FILES ))
            avis_telegram "OK $GEN: ${N_FILES} matchups in ${DURATION_MIN}m (${AVG_SEC}s/matchup)"

            if [ "$AVG_SEC" -gt "$MAX_TIME_PER_MATCHUP" ]; then
                avis_telegram "SLOW $GEN: avg ${AVG_SEC}s/matchup exceeds ${MAX_TIME_PER_MATCHUP}s threshold"
            fi
        else
            avis_telegram "FAIL $GEN attempt $ATTEMPT (exit $EXIT_CODE, ${DURATION_MIN}m)"
            # Full cleanup before retry
            cleanup
            # Extra wait on failure to let system stabilize
            sleep 10
        fi
    done

    if [ "$SUCCESS" = false ]; then
        avis_telegram "ABORT $GEN: failed $MAX_RETRIES attempts. Skipping."
    fi

    # Always clean between gens even on success (prevent RAM accumulation)
    cleanup
done

avis_telegram "ALL DONE. Results in $OUT_BASE/ ($(date '+%H:%M'))"
