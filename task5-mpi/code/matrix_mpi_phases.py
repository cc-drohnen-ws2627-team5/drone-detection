"""Matrix multiplication C = A x B with MPI, with separate times for the three phases.

Same computation as matrix_mpi.py (Task 5, example 2). matrix_mpi.py measures one
total time; this variant splits it into three phases, like the sequential and
parallel parts in the lecture's POV-Ray example (slide set 1, slide 54):

    distribute   rank 0 sends the row blocks of A (Scatter) and all of B (Bcast)
    compute      every process multiplies its rows of A with B
    collect      rank 0 receives the row blocks of C (Gather)

A barrier after "distribute" and after "compute" makes all processes wait until
every process has finished the phase, so the clock on rank 0 measures the whole
phase and not only the part of rank 0. Because of these two barriers the total
time can differ slightly from matrix_mpi.py; the measurement series were made
with matrix_mpi.py, this program only explains where the time goes.

Local test (Mac, conda environment cc-mpi):
    mpiexec -n 2 python matrix_mpi_phases.py 512

Arguments: matrix size n (rows = columns), optional seed (default 2026).
n must be divisible by the number of processes.
"""
import sys

import numpy as np
from mpi4py import MPI

TOLERANCE = 1e-10  # allowed relative error of the check, as in matrix_mpi.py


def check_product(rng, A, B, C):
    """Freivalds' test: compare C x with A (B x) for a random vector x."""
    x = rng.random(A.shape[1])
    expected = A @ (B @ x)
    return np.linalg.norm(C @ x - expected) / np.linalg.norm(expected)


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if len(sys.argv) < 2:
        if rank == 0:
            print("usage: mpiexec -n <processes> python matrix_mpi_phases.py <n> [seed]")
        return
    n = int(sys.argv[1])
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    if n % size != 0:
        if rank == 0:
            print(f"error: {n} rows cannot be split evenly over {size} processes")
        return
    rows = n // size  # rows of A (and of C) per process

    # Same setup as matrix_mpi.py: rank 0 creates A and B, the others reserve memory.
    if rank == 0:
        rng = np.random.default_rng(seed)
        A = rng.random((n, n))
        B = rng.random((n, n))
        C = np.empty((n, n))
    else:
        A = None
        B = np.empty((n, n))
        C = None
    A_local = np.empty((rows, n))

    comm.Barrier()  # start the stopwatch on all processes at the same time
    t_start = MPI.Wtime()

    # Phase 1, distribute
    comm.Scatter(A, A_local, root=0)
    comm.Bcast(B, root=0)
    comm.Barrier()            # wait until every process has received its data
    t_data = MPI.Wtime()

    # Phase 2, compute
    C_local = A_local @ B
    comm.Barrier()            # wait until every process has finished computing
    t_computed = MPI.Wtime()

    # Phase 3, collect (Gather returns on rank 0 only when all blocks have arrived)
    comm.Gather(C_local, C, root=0)

    t_end = MPI.Wtime()

    # Durations of the three phases; their sum is exactly t_end - t_start
    t_dist = t_data - t_start
    t_comp = t_computed - t_data
    t_coll = t_end - t_computed

    if rank == 0:
        t_total = t_end - t_start
        error = check_product(rng, A, B, C)
        print(f"C = A x B, n = {n}, {size} processes, total {t_total:.4f} s: "
              f"distribute {t_dist:.4f} s, compute {t_comp:.4f} s, collect {t_coll:.4f} s, "
              f"check error {error:.1e}")
        if error < TOLERANCE:
            # One line for the measurement script (easy to parse)
            print(f"RESULT processes={size} n={n} time_s={t_total:.6f} "
                  f"dist_s={t_dist:.6f} comp_s={t_comp:.6f} coll_s={t_coll:.6f}")
        else:
            print(f"ERROR check failed, relative error {error:.1e}")


if __name__ == "__main__":
    main()
