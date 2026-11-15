# Task 5: High-Performance LINPACK (HPL) and MPI

**Owner:** Kubilay (backup for Task 4: Monitoring)

## Goal

Measure the computing performance and the scalability of our Raspberry Pi cluster.

- Deploy MPI on the cluster (Open MPI on all Pis)
- Run the HPL benchmark and report the performance in GFLOPS
- Show the scalability of the worker nodes with two MPI examples:
  - Monte Carlo estimation of Pi (little communication)
  - Matrix multiplication (a lot of communication)
- Explain the results with Amdahl's law and Gustafson's law
- Analyze the achievable performance and the relevant bottlenecks
- Monitor the resource utilization with free, top, htop, iostat, netstat, vmstat and iotop

## Status (15 Nov 2026)

All measurements on the cluster are finished. Next: analysis, then documentation and poster.

| Step | Status |
|---|---|
| MPI setup and hello world | done (31 Oct): Open MPI and mpi4py on all 9 Pis, hello world with 32 processes |
| Example 1: Monte Carlo Pi | measured (14 Nov): 150 valid runs |
| Example 2: Matrix multiplication | measured (14 Nov): 150 valid runs |
| HPL benchmark | measured (14 Nov): see results below |
| Analysis (speedup, Amdahl, Gustafson) | next, until 2026-12-17 |
| Documentation and poster | draft in progress, until 2027-01-14 |

## First results

HPL (block size NB 64, reduction factor R = 0.7 as in Baun 2016, eq. 2, so the matrix uses about 50 % of the memory; at least 5 valid runs per row):

| Workers | Processes | GFLOPS (mean) | Speedup |
|---|---|---|---|
| 1 | 4 | 5.219 | 1.00 |
| 2 | 8 | 7.324 | 1.40 |
| 4 | 16 | 11.895 | 2.28 |
| 8 | 32 | 19.597 | 3.75 |

Findings so far (the full analysis follows):

- **Monte Carlo** scales almost ideally across Pis (1 process per Pi: speedup 2.00 with 2 Pis, 3.95 with 4 Pis), but much less inside one Pi (1.60 with 2 cores, 2.49 with 4 cores). The cores of one Pi 3 most likely slow each other down through shared memory access. The Raspberry Pi 3 cluster in the lecture shows the same pattern (Baun, slide set 1, slide 51: speedup 2.57 with 4 cores on one node).
- **Matrix multiplication** (n = 3072) gets slower again with more workers: 33.1 s with 1 process, 17.3 s with 2 and 4, 22.6 s with 8, 33.1 s with 16 and 32. netstat shows why: rank 0 sends matrix B through a single 100 Mbit/s link. The network is the bottleneck.
- **HPL** reaches a speedup of 3.75 with 8 workers. The share of CPU time spent in the operating system kernel rises from 1 % with 1 worker to 23 % with 8 workers (`vmstat`), so the 100 Mbit/s network limits HPL as well.
- **Heat:** without a fan the Pi 3 throttle above 80 °C under HPL. With one 120 mm USB fan the maximum was 62 °C.

## Measurement method

- 1, 2, 4 processes on one worker, then 8, 16, 32 processes on 2, 4, 8 workers (4 per worker). The master (Pi 4) starts the jobs but does not compute.
- Fixed problem sizes (Pi: 10^6 to 10^9 points, matrix: 512 to 3072) and a problem size that grows with the number of processes (Gustafson)
- 5 runs per configuration, mean value, wall clock time and `MPI_Wtime`
- A run is valid only if no worker throttled or had undervoltage during the run (HPL: also PASSED)
- Monitoring on every worker during each run: free, top, iostat, netstat and vmstat are logged automatically; htop and iotop are captured as screenshots during selected runs
- MPI traffic only over the wired network of the local switch (`eth0`); graphical desktop switched off on the workers during the measurement series (it was on during the control run with one process per Pi)

## Hardware and software

- Master node: Raspberry Pi 4 (8 GB), MPI master
- Worker nodes: 8x Raspberry Pi 3 Model B (4 cores, 1.2 GHz, about 905 MB usable RAM), 32 cores in total
- Network: 24-port Gigabit switch, but the Pi 3 only has 100 Mbit/s Ethernet (measured with iperf3: 94 Mbit/s)
- Cooling: one 120 mm USB fan on the highest level in front of both towers
- Software: Debian 13 (64 bit), Open MPI 5.0.7, mpi4py 4.0.3, NumPy 2.2.4, HPL 2.3 with OpenBLAS 0.3.29

## Folder structure

- `code/`: scripts
  - `pi_mpi.py`, `matrix_mpi.py`: the two MPI examples
  - `hpl_series.sh`, `hpl_monitor.sh`, `hpl_problem_size.py`: HPL runs and monitoring
  - `examples_series.sh`, `run_series_chain.sh`, `control_placement.sh`: measurement series for the examples
  - `demo_pi.sh`: live demo (Pi with 1 vs. 32 processes)
  - `install_packages.sh`, `journal_persistent.sh`, `hosts_workers.mpi`: cluster setup
  - `hello.py`, `pi_serial.py`: first tests
- `messungen/` (German for "measurements"):
  - `CC_T5_Messungen.csv`: all runs, with the columns `valid` and `quelle` (source)
  - `CC_T5_Netzwerk.csv`: network baseline (iperf3)
  - `rohdaten/` (raw data): results and logs from the cluster
- The documentation follows after my review.

## Note on AI use

I use an AI assistant (Claude) for this task. It wrote most of the helper scripts and, at my request, the core of `pi_mpi.py` and `matrix_mpi.py`. It drafted this README and the documentation and ran some commands on the cluster for me. I set up the hardware, made the decisions, checked the results and review all texts.
