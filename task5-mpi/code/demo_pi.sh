#!/bin/bash
# Live demo for Task 5 (not part of the measurement series, results are only printed).
# Computes pi with the Monte Carlo method (pi_mpi.py), first with 1 process on worker1,
# then, after pressing Enter, with 32 processes on all 8 workers (4 per worker).
#
# Start on the master:   bash /opt/mpi/demo_pi.sh              (200 million points)
#                        bash /opt/mpi/demo_pi.sh 400000000    (other number of points)
# Watch the load in a second terminal on the master:   ssh -t worker2 htop
# The number of points must be divisible by 32.

N=${1:-200000000}
export LC_ALL=C.UTF-8
MPI_OPTS="--mca btl_tcp_if_include eth0 --prtemca oob_tcp_if_include eth0 -x OPENBLAS_NUM_THREADS=1 -x OPENBLAS_CORETYPE=ARMV8 -x OMP_NUM_THREADS=1 -x LC_ALL"
ALL_WORKERS="worker1:4,worker2:4,worker3:4,worker4:4,worker5:4,worker6:4,worker7:4,worker8:4"

# One demo run. Arguments: number of processes, host list for mpirun
run_demo() {
    local p=$1 hosts=$2 t0 t1
    echo
    echo "=== $p process(es), $N points, hosts: $hosts ==="
    t0=$(date +%s.%N)
    mpirun --host "$hosts" -np "$p" $MPI_OPTS python3 /opt/mpi/pi_mpi.py "$N" | grep -v "^RESULT"
    t1=$(date +%s.%N)
    awk -v a="$t0" -v b="$t1" 'BEGIN { printf "wall clock time including MPI start: %.1f s\n", b - a }'
}

if [ $((N % 32)) -ne 0 ]; then
    echo "error: $N points cannot be split evenly over 32 processes"
    exit 1
fi

run_demo 1 "worker1:1"
echo
read -r -p "Press Enter to start the same calculation with 32 processes on 8 workers ... " || true
run_demo 32 "$ALL_WORKERS"
