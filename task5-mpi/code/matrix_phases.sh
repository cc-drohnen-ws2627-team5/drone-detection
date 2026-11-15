#!/bin/bash
# Phase times of the matrix example (Task 5, steps 8 and 9, bottlenecks).
# Question: the matrix series got slower again with more workers (n = 3072: 33.1 s with 1 process,
# 17.3 s with 4, 33.1 s with 32). The packet counters of netstat suggested that the 100 Mbit/s link
# of worker1 is the bottleneck, but this was only an estimate. matrix_mpi_phases.py measures the
# three phases separately (distribute, compute, collect), like the sequential and parallel parts in
# the lecture's POV-Ray example (slide set 1, slide 54).
# Same placement as examples_series.sh (1, 2, 4 processes on worker1, then 8, 16, 32 processes on
# 2, 4, 8 workers), same MPI options, monitoring (hpl_monitor.sh) and validity rule. The runs are
# interleaved, so that slow drifts affect all configurations alike.
#
# Start on the master inside tmux (about 30 minutes with the defaults):
#   tmux new -d -s phases 'bash /opt/mpi/matrix_phases.sh'
# Short test first (a few seconds per run):
#   SIZES=512 PROCS="1 4 8" RUNS=1 bash /opt/mpi/matrix_phases.sh
# Test of the logic without a cluster, prints the commands instead of running them:
#   DRY_RUN=1 OUT=/some/test/folder bash matrix_phases.sh
export LC_ALL=C.UTF-8

SIZES=${SIZES:-"1024 2048 3072"}         # matrix sizes of the series, divisible by 32
PROCS=${PROCS:-"1 2 4 8 16 32"}
RUNS=${RUNS:-5}
DRY_RUN=${DRY_RUN:-0}
PROGRAM=/opt/mpi/matrix_mpi_phases.py
MONITOR=/opt/mpi/hpl/hpl_monitor.sh
MPI_OPTS="--mca btl_tcp_if_include eth0 --prtemca oob_tcp_if_include eth0 -x OPENBLAS_NUM_THREADS=1 -x OPENBLAS_CORETYPE=ARMV8 -x OMP_NUM_THREADS=1 -x LC_ALL"

OUT=${OUT:-/opt/mpi/results/phases_$(date +%Y-%m-%d_%H%M)}
mkdir -p "$OUT/logs"
CSV="$OUT/results.csv"
echo "datum,beispiel,messart,umgebung,worker,prozesse,problemgroesse,lauf,zeit_wall_s,zeit_intern_s,ergebnis,notiz" > "$CSV"
exec > >(tee -a "$OUT/series.log") 2>&1

# In DRY_RUN mode, only print the command
run() { if [ "$DRY_RUN" = 1 ]; then echo "DRY: $*"; else "$@"; fi; }

echo "Phase measurement started $(date), results in $OUT"
echo "SIZES=$SIZES PROCS=$PROCS RUNS=$RUNS DRY_RUN=$DRY_RUN"

MAXP=0
for p in $PROCS; do
    for n in $SIZES; do
        if [ $((n % p)) -ne 0 ]; then echo "Stopped: $n rows cannot be split over $p processes"; exit 1; fi
    done
    [ "$p" -gt "$MAXP" ] && MAXP=$p
done
WMAX=$(( (MAXP + 3) / 4 ))

# Check before the measurement: same program on every worker used, throttling state, load,
# desktop on or off and available memory (the matrices of n = 3072 need about 430 MB on worker1)
if [ "$DRY_RUN" != 1 ]; then
    mpirun --version | head -1
    REF=$(md5sum "$PROGRAM" | cut -d' ' -f1)
    for i in $(seq 1 "$WMAX"); do
        h=worker$i
        sum=$(ssh -o ConnectTimeout=5 "$h" "md5sum $PROGRAM" 2>/dev/null | cut -d' ' -f1)
        state=$(ssh -o ConnectTimeout=5 "$h" "vcgencmd get_throttled; uptime; echo desktop=\$(systemctl is-active graphical.target); free -m | awk 'NR==2 {print \"available_mb=\" \$7}'" 2>/dev/null | tr '\n' ' ')
        echo "$h: ${state:-not reachable}"
        if [ "$sum" != "$REF" ]; then echo "Stopped: $PROGRAM on $h is missing or differs from the master"; exit 1; fi
    done
fi

# One run. Arguments: matrix size, processes, run number
run_one() {
    local n=$1 p=$2 run=$3
    local w=$(( (p + 3) / 4 ))
    local workers="" hosts="" i h s
    for i in $(seq 1 "$w"); do workers="$workers worker$i"; hosts="$hosts,worker$i:4"; done
    hosts=${hosts#,}                                             # as in examples_series.sh
    local seed=$((2026 + run))                                   # same seeds as the series
    local tag="n${n}_p${p}_run${run}"
    mkdir -p "$OUT/logs/$tag"

    for h in $workers; do run ssh "$h" "bash $MONITOR start"; done

    local t0 t1
    t0=$(date +%s.%N)
    run mpirun --host "$hosts" -np "$p" $MPI_OPTS python3 "$PROGRAM" "$n" "$seed" > "$OUT/logs/$tag/mpirun.out" 2>&1
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

    local wall line t_int dist comp coll gflops
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN {printf "%.3f", b - a}')
    line=$(grep -E "^RESULT" "$OUT/logs/$tag/mpirun.out" | head -1)
    t_int=$(echo "$line" | grep -o "time_s=[0-9.]*" | cut -d= -f2)
    dist=$(echo "$line" | grep -o "dist_s=[0-9.]*" | cut -d= -f2)
    comp=$(echo "$line" | grep -o "comp_s=[0-9.]*" | cut -d= -f2)
    coll=$(echo "$line" | grep -o "coll_s=[0-9.]*" | cut -d= -f2)
    [ -z "$line" ] && valid=no
    # GFLOPS as in matrix_mpi.py: a matrix product needs 2 n^3 operations
    gflops=$(awk -v n="$n" -v t="$t_int" 'BEGIN {if (t > 0) printf "%.6f", 2 * n * n * n / t / 1e9}')
    echo "$(date +%F),matrix_mpi,phasen,cluster_pi3,$w,$p,$n,$run,$wall,$t_int,$gflops,seed=$seed; dist_s=$dist; comp_s=$comp; coll_s=$coll; valid=$valid;$mon" >> "$CSV"
    echo "$(date '+%H:%M:%S') $tag: wall ${wall} s, total ${t_int:-?} s = distribute ${dist:-?} + compute ${comp:-?} + collect ${coll:-?}, valid=$valid"
}

for run in $(seq 1 "$RUNS"); do
    for n in $SIZES; do
        for p in $PROCS; do run_one "$n" "$p" "$run"; done
    done
done

TOTAL=$(( $(wc -l < "$CSV") - 1 ))
INVALID=$(grep -c "valid=no" "$CSV")
echo "Phase measurement finished $(date): $TOTAL runs, $INVALID not valid"
touch "$OUT/FINISHED"
