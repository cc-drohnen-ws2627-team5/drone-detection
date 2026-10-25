# Task 5: High-Performance LINPACK (HPL) and MPI

**Owner:** Kubilay (backup for Task 4: Monitoring)

## Goal

Measure the computing performance and the scalability of our Raspberry Pi cluster.

- Deploy MPI on the cluster (we use Open MPI)
- Run the HPL benchmark and report the performance in GFLOPS
- Show the scalability of the worker nodes with two MPI examples:
  - Monte Carlo estimation of Pi (little communication)
  - Matrix multiplication (a lot of communication)
- Explain the results with Amdahl's law and Gustafson's law
- Analyze the achievable performance and the relevant bottlenecks
- Monitor the resource utilization with free, top, htop, iostat, netstat, vmstat and iotop

## Measurement method (planned)

- Increase the number of CPU cores step by step (1, 2, 4, 8, 16, 32)
- Use several problem sizes, e.g. 1,000,000 up to 1,000,000,000 points for the Pi example
- Repeat every measurement 5 times and use the mean value
- Report the elapsed (wall clock) time and the speedup S(p) = T(1) / T(p)

This follows the Pi measurements in slide set 1 of the course.

## Hardware

- Master node: Raspberry Pi 4 (MPI master)
- Worker nodes: 8x Raspberry Pi 3 (MPI workers, 4 cores each, 32 cores in total)
- Network: Gigabit switch (the network ports of the Raspberry Pi 3 are slower, to be checked)

## Status

| Step | Deadline | Status |
|---|---|---|
| MPI setup and hello world | 2026-11-05 | in progress (local tests) |
| Example 1: Monte Carlo Pi | 2026-11-19 | planned |
| Example 2: Matrix multiplication | 2026-12-03 | planned |
| HPL benchmark | 2026-12-10 | planned |
| Analysis (speedup, Amdahl, Gustafson) | 2026-12-17 | planned |
| Documentation and poster | 2027-01-14 | planned |

## Planned folder structure

- `code/` MPI programs in Python (mpi4py)
- `results/` measurement data (CSV)
- `docs/` documentation

## Note on AI use

Parts of this documentation were drafted with the help of an AI assistant (Claude) and reviewed by me.
