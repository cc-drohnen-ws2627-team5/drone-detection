"""Monte Carlo approximation of pi with MPI (Task 5, example 1).

Idea (lecture slide set 1, slides 46 to 48): random points in the unit
square; the share of points inside the quarter circle is about pi/4.
Every MPI process throws its own points and counts its own hits.
Rank 0 combines the counts and computes pi.

Local test (Mac, conda environment cc-mpi):
    mpiexec -n 4 python pi_mpi.py 1000000

Arguments: total number of points, optional seed (default 2026).
The cluster command is in the Task 5 documentation.
"""
import sys

import numpy as np
from mpi4py import MPI

# Points per NumPy step. 1,000,000 points need about 16 MB (x and y),
# so even 10^9 points fit into the 905 MB of a Raspberry Pi 3
# with 4 processes per node.
CHUNK = 1_000_000


def count_hits(rng, num_points):
    """Return how many of num_points random points fall into the quarter circle."""
    hits = 0
    remaining = num_points
    while remaining > 0:
        m = min(CHUNK, remaining)
        x = rng.random(m)
        y = rng.random(m)
        hits += int(np.count_nonzero(x * x + y * y <= 1.0))
        remaining -= m
    return hits


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if len(sys.argv) < 2:
        if rank == 0:
            print("usage: mpiexec -n <processes> python pi_mpi.py <points> [seed]")
        return
    n = int(sys.argv[1])
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    if n % size != 0:
        if rank == 0:
            print(f"error: {n} points cannot be split evenly over {size} processes")
        return

    # Every process gets its own independent stream of random numbers.
    # With the same seed on every rank, all processes would throw exactly
    # the same points, and more processes would not improve the result.
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(size)[rank])

    comm.Barrier()  # start the stopwatch on all processes at the same time
    t_start = MPI.Wtime()

    # Split the work: every process throws the same share of the n points
    # and counts only its own hits.
    n_local = n // size
    local_hits = count_hits(rng, n_local)
    # Combine: rank 0 receives the sum of all hits (all other ranks get None).
    total_hits = comm.reduce(local_hits, op=MPI.SUM, root=0)
    if rank == 0:
        pi_estimate = 4 * total_hits / n

    t_end = MPI.Wtime()  # the internal time includes collecting the results

    if rank == 0:
        t_intern = t_end - t_start
        error = abs(pi_estimate - np.pi)
        print(f"Pi is about {pi_estimate:.8f} (error {error:.2e}), "
              f"{n} points, {size} processes, {t_intern:.4f} seconds")
        # One line for the measurement script (easy to parse)
        print(f"RESULT processes={size} points={n} pi={pi_estimate:.10f} "
              f"time_s={t_intern:.6f}")


if __name__ == "__main__":
    main()
