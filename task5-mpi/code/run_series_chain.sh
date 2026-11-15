#!/bin/bash
# Runs the remaining measurement series one after another without supervision (e.g. overnight):
#   1) waits until the newest HPL series (hpl_series.sh) has finished
#   2) Monte Carlo series (pi_mpi.py)
#   3) distributes /opt/mpi to the workers (matrix_mpi.py) and runs a short matrix test
#   4) matrix series, only if every run of the test was valid
# The pauses let the Raspberry Pis cool down and give every series its own results folder
# (the folder name contains the minute).
# Start on the master inside tmux:
#   tmux new -d -s chain 'bash /opt/mpi/run_series_chain.sh'
# Stop:
#   tmux kill-session -t chain
export LC_ALL=C.UTF-8
LOG=/opt/mpi/results/chain_$(date +%Y-%m-%d_%H%M).log
exec > >(tee -a "$LOG") 2>&1

HPL=$(ls -td /opt/mpi/results/hpl_* | head -1)
echo "$(date '+%F %T') waiting for $HPL/FINISHED"
while [ ! -f "$HPL/FINISHED" ]; do sleep 60; done

echo "$(date '+%F %T') HPL series finished, cooling pause"
sleep 120
echo "$(date '+%F %T') Monte Carlo series"
bash /opt/mpi/examples_series.sh

sleep 90
echo "$(date '+%F %T') distribute /opt/mpi to the workers"
for i in 1 2 3 4 5 6 7 8; do
    rsync -a --exclude results /opt/mpi/ "worker$i:/opt/mpi/" || echo "rsync to worker$i failed"
done

echo "$(date '+%F %T') short matrix test"
EXAMPLE=matrix SIZES=512 PROCS="1 4 8 32" RUNS=1 KINDS=fest bash /opt/mpi/examples_series.sh
TEST=$(ls -td /opt/mpi/results/matrix_* | head -1)
if [ ! -f "$TEST/FINISHED" ] || grep -q "valid=no" "$TEST/results.csv"; then
    echo "$(date '+%F %T') matrix test not valid, matrix series NOT started (see $TEST)"
    exit 1
fi

sleep 90
echo "$(date '+%F %T') matrix series"
EXAMPLE=matrix bash /opt/mpi/examples_series.sh
echo "$(date '+%F %T') chain finished"
