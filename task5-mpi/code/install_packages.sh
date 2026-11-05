#!/bin/bash
# Installs MPI, Python libraries and monitoring tools on one cluster node.
# Run on every node (master and workers): bash install_packages.sh [master]
# Tested on 2026-10-31 with Raspberry Pi OS (Debian 13 "trixie", arm64).
# libopenblas-dev (BLAS library for HPL) was installed the same day with a separate apt-get command.
set -e

PACKAGES="openmpi-bin libopenmpi-dev python3-mpi4py python3-numpy libopenblas-dev sysstat iotop iperf3"

# tmux keeps long runs alive on the master if the SSH connection drops
if [ "$1" = "master" ]; then
    PACKAGES="$PACKAGES tmux"
fi

sudo apt-get update
# noninteractive: iperf3 would otherwise ask whether to run as a daemon (answer: no)
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y $PACKAGES

mpirun --version | head -1
python3 -c "import mpi4py, numpy; print('mpi4py', mpi4py.__version__, 'numpy', numpy.__version__)"
