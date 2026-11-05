"""Problem size N for HPL, following Baun (2016), equation 2.

    N = sqrt(M * 1024^3 * X / 8) * R

M = main memory of one node in GB (Baun writes 1008 MB as 1.008),
X = number of nodes, R = reduction factor.
Afterwards N is rounded down to a multiple of the block size NB.

Check with Baun's own example (2016, p. 17): M = 1.008, X = 4, R = 0.8, NB = 64
must give N = 18560.
"""
import math
import sys


def hpl_problem_size(mem_gb, nodes, r, nb):
    n = math.sqrt(mem_gb * 1024**3 * nodes / 8) * r
    return int(n // nb) * nb


if __name__ == "__main__":
    # usage: python3 hpl_problem_size.py <mem_gb> <nodes> <r> <nb>
    mem_gb = float(sys.argv[1])
    nodes = int(sys.argv[2])
    r = float(sys.argv[3])
    nb = int(sys.argv[4])
    n = hpl_problem_size(mem_gb, nodes, r, nb)
    print(n)
    # the matrix has N * N numbers of 8 bytes, spread over all nodes
    print(f"matrix per node: {n * n * 8 / nodes / 1024**2:.0f} MiB", file=sys.stderr)
