import random
import time

n = 10_000_000
hits = 0

start = time.time()
for i in range(n):
    x = random.random()
    y = random.random()
    if x * x + y * y <= 1.0:
        hits = hits + 1
duration = time.time() - start

pi = 4 * hits / n
print(f"Pi is about {pi} ({n} points, {duration:.2f} seconds)")