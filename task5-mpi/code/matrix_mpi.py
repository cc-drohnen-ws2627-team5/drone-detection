"""Distributed matrix multiplication C = A x B with MPI (Task 5, example 2).

Counterpart to pi_mpi.py: Monte Carlo sends almost nothing, here a lot of
data has to travel. Every process needs all of B and one block of rows of A,
and it sends back one block of rows of C. For n x n matrices the work grows
with n^3, the data to send with n^2.

Rank 0 creates two random n x n matrices A and B. A is split into row
blocks of equal size: process i multiplies its block of A with B and returns
the matching block of C. Rank 0 checks the result (Freivalds' test).

Local test (Mac, conda environment cc-mpi):
    mpiexec -n 4 python matrix_mpi.py 512

Arguments: matrix size n (rows = columns), optional seed (default 2026).
n must be divisible by the number of processes.
On the cluster the measurement script sets one BLAS thread per process and
OPENBLAS_CORETYPE=ARMV8 (the Cortex-A53 routines of OpenBLAS 0.3.29 gave
wrong results with HPL, see documentation section 10).
"""
import sys

import numpy as np
from mpi4py import MPI

# Allowed relative error of the check. Doubles carry about 16 digits; the
# rounding errors of sums over n products stay far below this value.
TOLERANCE = 1e-10


def check_product(rng, A, B, C):
    """Freivalds' test: compare C x with A (B x) for a random vector x.

    Needs only matrix-vector products (about n^2 operations instead of n^3),
    so the check is much faster than computing A @ B a second time.
    Returns the relative error.
    """
    x = rng.random(A.shape[1])
    expected = A @ (B @ x)
    return np.linalg.norm(C @ x - expected) / np.linalg.norm(expected)


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if len(sys.argv) < 2:
        if rank == 0:
            print("usage: mpiexec -n <processes> python matrix_mpi.py <n> [seed]")
        return
    n = int(sys.argv[1])
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    if n % size != 0:
        if rank == 0:
            print(f"error: {n} rows cannot be split evenly over {size} processes")
        return
    rows = n // size  # rows of A (and of C) per process

    # Rank 0 creates the full matrices. The other ranks only reserve memory:
    # a full B (every process needs all of B). MPI writes received data into
    # existing NumPy arrays, so every receiving buffer must exist beforehand.
    if rank == 0:
        rng = np.random.default_rng(seed)
        A = rng.random((n, n))
        B = rng.random((n, n))
        C = np.empty((n, n))
    else:
        A = None
        B = np.empty((n, n))
        C = None
    A_local = np.empty((rows, n))  # this process's block of rows of A

    comm.Barrier()  # start the stopwatch on all processes at the same time
    t_start = MPI.Wtime()

    # Distribute: rank 0 cuts A into equal blocks of rows, one per process,
    # and sends all of B to every process (the expensive part: n * n numbers each).
    comm.Scatter(A, A_local, root=0)
    comm.Bcast(B, root=0)
    # Compute: every process multiplies its rows of A with B, which gives
    # exactly its rows of C.
    C_local = A_local @ B
    # Collect: rank 0 puts the blocks of C together in rank order.
    comm.Gather(C_local, C, root=0)

    t_end = MPI.Wtime()  # the internal time includes sending and collecting

    if rank == 0:
        t_intern = t_end - t_start
        gflops = 2 * n**3 / t_intern / 1e9  # a matrix product needs 2 n^3 operations
        error = check_product(rng, A, B, C)
        print(f"C = A x B, n = {n}, {size} processes, {t_intern:.4f} seconds, "
              f"{gflops:.3f} GFLOPS, check error {error:.1e}")
        if error < TOLERANCE:
            # One line for the measurement script (easy to parse)
            print(f"RESULT processes={size} n={n} gflops={gflops:.6f} "
                  f"time_s={t_intern:.6f}")
        else:
            # No RESULT line: the measurement script marks the run as not valid
            print(f"ERROR check failed, relative error {error:.1e}")


if __name__ == "__main__":
    main()
