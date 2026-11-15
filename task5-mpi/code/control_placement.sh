#!/bin/bash
# Control measurement for Task 5 (steps 8 and 9, bottlenecks).
# Question: why does the speedup grow so little inside one worker (Monte Carlo with 10^9 points:
# 2.45 with 4 processes on worker1, wall clock), while every doubling of the workers almost halves
# the time? The same job (pi_mpi.py) runs with 2 and 4 processes, once "kompakt" (all processes on
# worker1, as in the series) and once "verteilt" (one process per worker, on 2 or 4 workers).
# If "verteilt" is clearly faster, the processes slow each other down inside one Raspberry Pi 3
# (a shared resource such as the memory interface), not MPI and not the network.
# 1 process runs once per round as the reference t(1) of this session.
# Same MPI options, monitoring (hpl_monitor.sh) and validity rule as examples_series.sh.
# The configurations run interleaved, so that slow drifts affect all of them alike.
#
# Start on the master inside tmux (about 35 minutes with the defaults):
#   tmux new -d -s ctl 'bash /opt/mpi/control_placement.sh'
# Short test first (a few seconds per run):
#   N=10000000 RUNS=1 bash /opt/mpi/control_placement.sh
# Test of the logic without a cluster, prints the commands instead of running them:
#   DRY_RUN=1 OUT=/some/test/folder bash control_placement.sh
export LC_ALL=C.UTF-8

N=${N:-1000000000}                       # points, the largest size of the series
PROCS=${PROCS:-"1 2 4"}                  # at most 4: "kompakt" puts all processes on worker1
PLACEMENTS=${PLACEMENTS:-"kompakt verteilt"}
RUNS=${RUNS:-5}
DRY_RUN=${DRY_RUN:-0}
PROGRAM=/opt/mpi/pi_mpi.py
MONITOR=/opt/mpi/hpl/hpl_monitor.sh
MPI_OPTS="--mca btl_tcp_if_include eth0 --prtemca oob_tcp_if_include eth0 -x OPENBLAS_NUM_THREADS=1 -x OPENBLAS_CORETYPE=ARMV8 -x OMP_NUM_THREADS=1 -x LC_ALL"

OUT=${OUT:-/opt/mpi/results/control_$(date +%Y-%m-%d_%H%M)}
mkdir -p "$OUT/logs"
CSV="$OUT/results.csv"
echo "datum,beispiel,messart,umgebung,worker,prozesse,problemgroesse,lauf,zeit_wall_s,zeit_intern_s,ergebnis,notiz" > "$CSV"
exec > >(tee -a "$OUT/series.log") 2>&1

# In DRY_RUN mode, only print the command
run() { if [ "$DRY_RUN" = 1 ]; then echo "DRY: $*"; else "$@"; fi; }

echo "Control measurement started $(date), results in $OUT"
echo "N=$N PROCS=$PROCS PLACEMENTS=$PLACEMENTS RUNS=$RUNS DRY_RUN=$DRY_RUN"

MAXP=0
for p in $PROCS; do
    if [ "$p" -gt 4 ]; then echo "Stopped: $p processes do not fit on worker1 (4 cores)"; exit 1; fi
    if [ $((N % p)) -ne 0 ]; then echo "Stopped: $N points cannot be split over $p processes"; exit 1; fi
    [ "$p" -gt "$MAXP" ] && MAXP=$p
done

# Check before the measurement: same program on every worker used, throttling state and load
if [ "$DRY_RUN" != 1 ]; then
    mpirun --version | head -1
    REF=$(md5sum "$PROGRAM" | cut -d' ' -f1)
    for i in $(seq 1 "$MAXP"); do
        h=worker$i
        sum=$(ssh -o ConnectTimeout=5 "$h" "md5sum $PROGRAM" 2>/dev/null | cut -d' ' -f1)
        state=$(ssh -o ConnectTimeout=5 "$h" "vcgencmd get_throttled; uptime" 2>/dev/null | tr '\n' ' ')
        echo "$h: ${state:-not reachable}"
        if [ "$sum" != "$REF" ]; then echo "Stopped: $PROGRAM on $h is missing or differs from the master"; exit 1; fi
    done
fi

# One run. Arguments: placement (kompakt or verteilt), processes, run number
run_one() {
    local placement=$1 p=$2 run=$3
    local workers="" hosts="" i h s w
    if [ "$placement" = kompakt ]; then
        workers="worker1"; hosts="worker1:4"; w=1               # as in examples_series.sh
    else
        for i in $(seq 1 "$p"); do workers="$workers worker$i"; hosts="$hosts,worker$i:1"; done
        hosts=${hosts#,}; w=$p
    fi
    local seed=$((2026 + run))                                   # same seeds as the series
    local tag="${placement}_n${N}_p${p}_run${run}"
    mkdir -p "$OUT/logs/$tag"

    for h in $workers; do run ssh "$h" "bash $MONITOR start"; done

    local t0 t1
    t0=$(date +%s.%N)
    run mpirun --host "$hosts" -np "$p" $MPI_OPTS python3 "$PROGRAM" "$N" "$seed" > "$OUT/logs/$tag/mpirun.out" 2>&1
    t1=$(date +%s.%N)

    local mon="" valid=yes
    for h in $workers; do
        s=$(run ssh "$h" "bash $MONITOR stop")
        mon="$mon $h:$s"
        case $s in
            "throttle_now_s=0 "*) ;;
            *) valid=no ;;
        esac
        run rsync -a "$h:/tmp/mon_*.log" "$OUT/logs/$tag/$h/" 2>/dev/null
    done

    local wall line t_int result
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN {printf "%.3f", b - a}')
    line=$(grep -E "^RESULT" "$OUT/logs/$tag/mpirun.out" | head -1)
    t_int=$(echo "$line" | grep -o "time_s=[0-9.]*" | cut -d= -f2)
    result=$(echo "$line" | grep -o "pi=[0-9.]*" | cut -d= -f2)
    [ -z "$line" ] && valid=no
    echo "$(date +%F),monte_carlo_mpi,kontrolle,cluster_pi3,$w,$p,$N,$run,$wall,$t_int,$result,seed=$seed; verteilung=$placement; valid=$valid;$mon" >> "$CSV"
    echo "$(date '+%H:%M:%S') $tag: hosts $hosts, wall ${wall} s, intern ${t_int:-?} s, valid=$valid"
}

for run in $(seq 1 "$RUNS"); do
    for p in $PROCS; do
        if [ "$p" = 1 ]; then
            run_one kompakt 1 "$run"                             # 1 process: both placements are the same
        else
            for placement in $PLACEMENTS; do run_one "$placement" "$p" "$run"; done
        fi
    done
done

TOTAL=$(( $(wc -l < "$CSV") - 1 ))
INVALID=$(grep -c "valid=no" "$CSV")
echo "Control measurement finished $(date): $TOTAL runs, $INVALID not valid"
touch "$OUT/FINISHED"
