#!/bin/bash
# HPL measurement series on the Raspberry Pi 3 workers, following Baun (2016):
#   1) block size sweep (NB) on all 8 workers, one run per NB
#   2) 1, 2, 4 and 8 workers with the best NB, RUNS runs each (interleaved)
# Start on the master inside tmux:
#   tmux new -d -s hpl 'bash /opt/mpi/hpl/hpl_series.sh'
export LC_ALL=C.UTF-8

HPL_DIR=/opt/mpi/hpl
OUT=/opt/mpi/results/hpl_$(date +%Y-%m-%d_%H%M)
MEM_GB=0.905     # main memory of one Raspberry Pi 3 (free -m: 905 MB), written like Baun (1008 MB = 1.008)
# reduction factor (Baun 2016, eq. 2). Baun used 0.8; with 0.8 the free memory of all workers
# fell to about 22 MB and one worker rebooted (see section 10), so 0.7 leaves about 140 MB more.
R=${R:-0.7}
RUNS=${RUNS:-5}
NB_SWEEP=${NB_SWEEP-"16 32 64 128 256"}   # set but empty (NB_SWEEP="") skips the sweep
# single heat test run (8 workers, NB 128, no series):
#   NB_SWEEP=128 RUNS=0 bash /opt/mpi/hpl/hpl_series.sh
# repeat single configurations later without a new sweep, e.g.:
#   NB_SWEEP="" BEST_NB=64 WORKER_COUNTS="4" RUNS=3 bash /opt/mpi/hpl/hpl_series.sh
WORKER_COUNTS=${WORKER_COUNTS:-"1 2 4 8"}
# OPENBLAS_CORETYPE=ARMV8: the Cortex-A53 kernels of OpenBLAS 0.3.29 gave wrong results (see section 10)
MPI_OPTS="--mca btl_tcp_if_include eth0 --prtemca oob_tcp_if_include eth0 -x OPENBLAS_NUM_THREADS=1 -x OPENBLAS_CORETYPE=ARMV8 -x LC_ALL"

mkdir -p "$OUT/logs"
CSV="$OUT/hpl_results.csv"
echo "datum,beispiel,messart,umgebung,worker,prozesse,problemgroesse,lauf,zeit_wall_s,zeit_intern_s,ergebnis,notiz" > "$CSV"
exec > >(tee -a "$OUT/series.log") 2>&1

# Process grid P x Q for a number of workers (4 cores each), as in Baun (2016), Table 5
grid() {
    case $1 in
        1) echo "1 4" ;;
        2) echo "2 4" ;;
        4) echo "2 8" ;;
        8) echo "4 8" ;;
    esac
}

write_hpl_dat() {  # arguments: N NB P Q
    cat > "$OUT/HPL.dat" <<EOF
HPLinpack benchmark input file
Innovative Computing Laboratory, University of Tennessee
HPL.out      output file name (if any)
6            device out (6=stdout,7=stderr,file)
1            # of problems sizes (N)
$1           Ns
1            # of NBs
$2           NBs
0            PMAP process mapping (0=Row-,1=Column-major)
1            # of process grids (P x Q)
$3           Ps
$4           Qs
16.0         threshold
1            # of panel fact
2            PFACTs (0=left, 1=Crout, 2=Right)
1            # of recursive stopping criterium
4            NBMINs (>= 1)
1            # of panels in recursion
2            NDIVs
1            # of recursive panel fact.
1            RFACTs (0=left, 1=Crout, 2=Right)
1            # of broadcast
1            BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)
1            # of lookahead depth
1            DEPTHs (>=0)
2            SWAP (0=bin-exch,1=long,2=mix)
64           swapping threshold
0            L1 in (0=transposed,1=no-transposed) form
0            U  in (0=transposed,1=no-transposed) form
1            Equilibration (0=no,1=yes)
8            memory alignment in double (> 0)
EOF
}

# One HPL run. Arguments: kind (nb_sweep or series), number of workers, NB, run number
run_hpl() {
    local kind=$1 w=$2 nb=$3 run=$4 p q n i h
    read -r p q <<< "$(grid "$w")"
    n=$(python3 "$HPL_DIR/hpl_problem_size.py" "$MEM_GB" "$w" "$R" "$nb" 2>/dev/null)
    local workers="" hosts=""
    for i in $(seq 1 "$w"); do workers="$workers worker$i"; hosts="$hosts,worker$i:4"; done
    hosts=${hosts#,}
    local tag="${kind}_w${w}_nb${nb}_run${run}"
    mkdir -p "$OUT/logs/$tag"
    write_hpl_dat "$n" "$nb" "$p" "$q"

    for h in $workers; do
        ssh "$h" "mkdir -p /tmp/hplrun" && scp -q "$OUT/HPL.dat" "$h:/tmp/hplrun/HPL.dat"
        ssh "$h" "bash $HPL_DIR/hpl_monitor.sh start"
    done

    echo "$(date '+%H:%M:%S') start $tag: N=$n NB=$nb P=$p Q=$q"
    local t0 t1
    t0=$(date +%s.%N)
    mpirun --host "$hosts" -np $((4 * w)) --wdir /tmp/hplrun $MPI_OPTS "$HPL_DIR/xhpl" > "$OUT/logs/$tag/hpl.out" 2>&1
    t1=$(date +%s.%N)

    local mon=""
    for h in $workers; do
        mon="$mon $h:$(ssh "$h" "bash $HPL_DIR/hpl_monitor.sh stop")"
        rsync -a "$h:/tmp/mon_*.log" "$OUT/logs/$tag/$h/" 2>/dev/null
    done

    local wall line t_hpl gflops check
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN {printf "%.2f", b - a}')
    line=$(grep -E "^WR" "$OUT/logs/$tag/hpl.out" | head -1)
    t_hpl=$(echo "$line" | awk '{print $6}')
    gflops=$(echo "$line" | awk '{print $7}')
    check=$(grep -o -E "PASSED|FAILED" "$OUT/logs/$tag/hpl.out" | head -1)
    echo "$(date +%F),hpl,$kind,cluster_pi3,$w,$((4 * w)),$n,$run,$wall,$t_hpl,$gflops,NB=$nb; P=$p; Q=$q; R=$R; check=${check:-none};$mon" >> "$CSV"
    echo "$(date '+%H:%M:%S') done  $tag: ${t_hpl:-?} s, ${gflops:-?} GFLOPS, ${check:-no result}"
}

echo "HPL series started $(date), results in $OUT"

# 1) block size sweep on all 8 workers
for nb in $NB_SWEEP; do
    run_hpl nb_sweep 8 "$nb" 1
done

# best NB = highest GFLOPS among the passed runs of the sweep, unless given from outside (BEST_NB=64)
if [ -z "$BEST_NB" ]; then
    BEST_NB=$(awk -F, '$3 == "nb_sweep" && $12 ~ /check=PASSED/ {
        split($12, a, ";"); sub("NB=", "", a[1])
        if ($11 + 0 > max) { max = $11 + 0; nb = a[1] }
    } END { print nb }' "$CSV")
fi
BEST_NB=${BEST_NB:-128}
echo "best NB: $BEST_NB"

# 2) 1, 2, 4 and 8 workers, runs interleaved so that slow drifts affect all worker counts alike
for run in $(seq 1 "$RUNS"); do
    for w in $WORKER_COUNTS; do
        run_hpl series "$w" "$BEST_NB" "$run"
    done
done

echo "HPL series finished $(date)"
touch "$OUT/FINISHED"
