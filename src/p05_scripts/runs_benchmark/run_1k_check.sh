#!/bin/bash
# run_1k_check.sh — Quick sanity check: 1k games across all 9 gens.
#
# Writes to the SAME output folder as run_all_10k.sh (benchmarks_all_10k/).
# When satisfied, just run run_all_10k.sh — it will top up each matchup
# from 1k to 10k automatically via benchmark.py's resume logic.
#
# Estimated time: ~5-6 hours

if grep -q 'avis_telegram()' ~/.bashrc 2>/dev/null; then
    eval "$(grep -A3 '^avis_telegram()' ~/.bashrc)"
else
    avis_telegram() { echo "[NOTIFY] $1"; }
fi

GENS="gen1randombattle gen2randombattle gen3randombattle gen4randombattle gen5randombattle gen6randombattle gen7randombattle gen8randombattle gen9randombattle"
AGENTS="v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 random max_power abyssal one_step safe_one_step simple_heuristic"
N_BATTLES=1000
PORTS=8
CONCURRENCY=20
OUT_BASE="data/1_vs_1/benchmarks_all_10k"   # SAME folder as run_all_10k.sh
MAX_RETRIES=3

cleanup() {
    pkill -f "pokemon-showdown" 2>/dev/null
    pkill -f "worker.py" 2>/dev/null
    for PORT in $(seq 8000 $((8000 + PORTS - 1))); do
        fuser -k "${PORT}/tcp" 2>/dev/null
    done
    pkill -f "s01_singles/evaluation/engine" 2>/dev/null
    sleep 5
    sync
    echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1 || true
}

trap 'cleanup; avis_telegram "KILLED: 1k check was terminated. Re-run to resume."; exit 1' SIGTERM SIGINT SIGHUP

TOTAL_START=$(date +%s)
avis_telegram "Starting 1k sanity check: 18 agents × 9 gens × 1000 games (~5h) | $(date '+%H:%M')"

cleanup

for GEN in $GENS; do
    avis_telegram "[${GEN}] Starting 1k check"
    START_GEN=$(date +%s)
    GEN_AGENTS_DONE=0

    for AGENT in $AGENTS; do
        ATTEMPT=0
        SUCCESS=false

        while [ $ATTEMPT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
            ATTEMPT=$(( ATTEMPT + 1 ))
            [ $ATTEMPT -gt 1 ] && { cleanup; sleep 5; }

            uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py \
                $N_BATTLES \
                --agents "$AGENT" \
                --opponents $AGENTS \
                --ports $PORTS \
                --concurrency $CONCURRENCY \
                --battle-format "$GEN" \
                --out "${OUT_BASE}/${GEN}" \
                --restart-every 3
            EXIT_CODE=$?

            if [ $EXIT_CODE -eq 0 ]; then
                SUCCESS=true
                GEN_AGENTS_DONE=$(( GEN_AGENTS_DONE + 1 ))
            else
                avis_telegram "[${GEN}] ${AGENT} FAIL attempt ${ATTEMPT}"
                cleanup
            fi
        done
    done

    END_GEN=$(date +%s)
    GEN_MIN=$(( (END_GEN - START_GEN) / 60 ))
    avis_telegram "[${GEN}] 1k check DONE in ${GEN_MIN}m (${GEN_AGENTS_DONE}/18 agents ok)"
    cleanup
done

TOTAL_END=$(date +%s)
TOTAL_MIN=$(( (TOTAL_END - TOTAL_START) / 60 ))
avis_telegram "1k CHECK COMPLETE in ${TOTAL_MIN}m. Review data in ${OUT_BASE}/, then run run_all_10k.sh to top up to 10k. | $(date '+%H:%M')"
echo ""
echo "Next step: review the CSVs, then run:"
echo "  bash src/p05_scripts/run_all_10k.sh 2>&1 | tee benchmark_log.txt"
