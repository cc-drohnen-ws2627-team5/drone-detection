#!/bin/bash
# Measurement series for the MPI examples on the Raspberry Pi 3 workers (Task 5, steps 6 and 8).
# Method: see "Measurement method" in the documentation.
#   fest      fixed problem sizes over orders of magnitude, 1 to 32 processes
#             (Amdahl's law; comparing the sizes shows Gustafson's law, lecture slide set 1, slide 48)
#   wachsend  the work per process stays the same, the total size grows with the processes (Gustafson)
# 1, 2 and 4 processes run on worker1, 8, 16 and 32 processes on 2, 4 and 8 workers (4 per worker).
# The master only starts the jobs. Every configuration runs RUNS times, interleaved, so that slow
# drifts affect all configurations alike. hpl_monitor.sh records on every worker used; a run is
# valid if it printed a result and no worker had a current throttling bit.
#
# Start on the master inside tmux:
#   tmux new -d -s mc 'bash /opt/mpi/examples_series.sh'                  (Monte Carlo, pi_mpi.py)
#   tmux new -d -s mm 'EXAMPLE=matrix bash /opt/mpi/examples_series.sh'   (matrix_mpi.py)
# Short test first:
#   SIZES=1000000 PROCS="1 4 8" RUNS=1 KINDS=fest bash /opt/mpi/examples_series.sh
#   EXAMPLE=matrix SIZES=512 PROCS="1 4 8" RUNS=1 KINDS=fest bash /opt/mpi/examples_series.sh
export LC_ALL=C.UTF-8

EXAMPLE=${EXAMPLE:-pi}
RUNS=${RUNS:-5}
PROCS=${PROCS:-"1 2 4 8 16 32"}
KINDS=${KINDS:-"fest wachsend"}
PAUSE=${PAUSE:-0}                  # seconds of cooling between two runs, 0 = no pause
MONITOR=/opt/mpi/hpl/hpl_monitor.sh
# one thread per process (OpenBLAS, OpenMP), MPI traffic only over eth0.
# OPENBLAS_CORETYPE=ARMV8: the Cortex-A53 routines of OpenBLAS 0.3.29 gave wrong results with HPL
# (section 10); the matrix product of NumPy in matrix_mpi.py can use OpenBLAS as well.
MPI_OPTS="--mca btl_tcp_if_include eth0 --prtemca oob_tcp_if_include eth0 -x OPENBLAS_NUM_THREADS=1 -x OPENBLAS_CORETYPE=ARMV8 -x OMP_NUM_THREADS=1 -x LC_ALL"

case $EXAMPLE in
pi)
    PROGRAM=/opt/mpi/pi_mpi.py
    NAME=monte_carlo_mpi
    RESULT_KEY=pi
    SIZES=${SIZES:-"1000000 10000000 100000000 1000000000"}   # total points (fest)
    PER_PROC=${PER_PROC:-50000000}                             # points per process (wachsend)
    ;;
matrix)
    PROGRAM=/opt/mpi/matrix_mpi.py
    NAME=matrix_mpi
    RESULT_KEY=gflops
    SIZES=${SIZES:-"512 1024 2048 3072"}   # matrix size n (fest), divisible by 32
    # wachsend: the work per process (n^3 / p) stays the same, so n grows with the cube root
    # of p: n = 1024 * p^(1/3), rounded to a multiple of p. Format processes:n
    GROW=${GROW:-"1:1024 2:1290 4:1624 8:2048 16:2576 32:3264"}
    ;;
*)
    echo "unknown EXAMPLE: $EXAMPLE"
    exit 1
    ;;
esac

OUT=/opt/mpi/results/${EXAMPLE}_$(date +%Y-%m-%d_%H%M)
mkdir -p "$OUT/logs" "$OUT/before"
CSV="$OUT/results.csv"
echo "datum,beispiel,messart,umgebung,worker,prozesse,problemgroesse,lauf,zeit_wall_s,zeit_intern_s,ergebnis,notiz" > "$CSV"
exec > >(tee -a "$OUT/series.log") 2>&1

echo "Series $EXAMPLE started $(date), results in $OUT"
echo "RUNS=$RUNS PROCS=$PROCS KINDS=$KINDS SIZES=$SIZES PER_PROC=$PER_PROC GROW=$GROW PAUSE=$PAUSE"
mpirun --version | head -1
python3 -c "import mpi4py, numpy; print('mpi4py', mpi4py.__version__, 'numpy', numpy.__version__)"

# Workers needed for the largest process count (4 processes per worker)
MAXP=0
for p in $PROCS; do [ "$p" -gt "$MAXP" ] && MAXP=$p; done
WMAX=$(( (MAXP + 3) / 4 ))

# Check before the series: same program on every worker, throttling state, load, process list
REF=$(md5sum "$PROGRAM" | cut -d' ' -f1)
OK=yes
for i in $(seq 1 "$WMAX"); do
    h=worker$i
    sum=$(ssh -o ConnectTimeout=5 "$h" "md5sum $PROGRAM" 2>/dev/null | cut -d' ' -f1)
    state=$(ssh -o ConnectTimeout=5 "$h" "vcgencmd get_throttled; uptime" 2>/dev/null | tr '\n' ' ')
    echo "$h: ${state:-not reachable}"
    ssh -o ConnectTimeout=5 "$h" "top -b -n 1 -w 200 | head -n 15" > "$OUT/before/${h}_top.txt" 2>&1
    if [ "$sum" != "$REF" ]; then
        echo "  $h: $PROGRAM is missing or differs from the master"
        OK=no
    fi
    case $state in
        throttled=0x0\ *) ;;
        *) echo "  $h: throttling bits set since boot (a reboot resets them)" ;;
    esac
done
if [ "$OK" != yes ]; then
    echo "Stopped. Distribute the program first: for i in 1 2 3 4 5 6 7 8; do rsync -a /opt/mpi/ worker\$i:/opt/mpi/; done"
    exit 1
fi

# Problem size for kind wachsend: from the GROW list (matrix) or PER_PROC * processes (pi)
grow_size() {
    local p=$1 e
    if [ -n "$GROW" ]; then
        for e in $GROW; do
            if [ "${e%%:*}" = "$p" ]; then echo "${e#*:}"; return 0; fi
        done
        echo "no GROW size for $p processes" >&2
        return 1
    fi
    echo $((PER_PROC * p))
}

# One run. Arguments: kind (fest or wachsend), processes, problem size, run number
run_one() {
    local kind=$1 p=$2 n=$3 run=$4
    local w=$(( (p + 3) / 4 ))
    local workers="" hosts="" i h s
    for i in $(seq 1 "$w"); do workers="$workers worker$i"; hosts="$hosts,worker$i:4"; done
    hosts=${hosts#,}
    local seed=$((2026 + run))
    local tag="${kind}_n${n}_p${p}_run${run}"
    mkdir -p "$OUT/logs/$tag"

    for h in $workers; do ssh "$h" "bash $MONITOR start"; done

    local t0 t1
    t0=$(date +%s.%N)
    mpirun --host "$hosts" -np "$p" $MPI_OPTS python3 "$PROGRAM" "$n" "$seed" > "$OUT/logs/$tag/mpirun.out" 2>&1
    t1=$(date +%s.%N)

    local mon="" valid=yes
    for h in $workers; do
        s=$(ssh "$h" "bash $MONITOR stop")
        mon="$mon $h:$s"
        case $s in
            "throttle_now_s=0 "*) ;;
            *) valid=no ;;
        esac
        rsync -a "$h:/tmp/mon_*.log" "$OUT/logs/$tag/$h/" 2>/dev/null
    done

    local wall line t_int result
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN {printf "%.3f", b - a}')
    line=$(grep -E "^RESULT" "$OUT/logs/$tag/mpirun.out" | head -1)
    t_int=$(echo "$line" | grep -o "time_s=[0-9.]*" | cut -d= -f2)
    result=$(echo "$line" | grep -o "$RESULT_KEY=[0-9.]*" | cut -d= -f2)
    [ -z "$line" ] && valid=no
    echo "$(date +%F),$NAME,$kind,cluster_pi3,$w,$p,$n,$run,$wall,$t_int,$result,seed=$seed; valid=$valid;$mon" >> "$CSV"
    echo "$(date '+%H:%M:%S') $tag: wall ${wall} s, intern ${t_int:-?} s, $RESULT_KEY=${result:-none}, valid=$valid"
    if [ "$PAUSE" -gt 0 ]; then sleep "$PAUSE"; fi
}

for run in $(seq 1 "$RUNS"); do
    for kind in $KINDS; do
        case $kind in
        fest)
            for n in $SIZES; do
                for p in $PROCS; do run_one fest "$p" "$n" "$run"; done
            done
            ;;
        wachsend)
            for p in $PROCS; do run_one wachsend "$p" "$(grow_size "$p")" "$run"; done
            ;;
        esac
    done
done

TOTAL=$(( $(wc -l < "$CSV") - 1 ))
INVALID=$(grep -c "valid=no" "$CSV")
echo "Series finished $(date): $TOTAL runs, $INVALID not valid"
touch "$OUT/FINISHED"
