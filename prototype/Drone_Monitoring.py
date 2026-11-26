# Block 1 - CPU Information
import os

print("Drone Detection - Monitoring")
print("CPU cores:", os.cpu_count())

# Block 2 - CPU Usage
import subprocess

result = subprocess.run(
    ["top", "-l", "2", "-n", "0"],
    capture_output=True,
    text=True
)

for line in result.stdout.splitlines():
    if "CPU usage:" in line:
        print(line)


# Block 3 - RAM Monitoring

import subprocess

result = subprocess.run(
    ["memory_pressure"],
    capture_output=True,
    text=True
)

print("RAM Monitoring:")
print(result.stdout)
print("Errors:", result.stderr)


# Block 4 - Save CPU and RAM Data to CSV

import csv
import re
import subprocess
from datetime import datetime
from pathlib import Path

# Read CPU usage
cpu_result = subprocess.run(
    ["top", "-l", "2", "-n", "0"],
    capture_output=True,
    text=True
)

cpu_lines = [
    line for line in cpu_result.stdout.splitlines()
    if "CPU usage:" in line
]

cpu_usage = None

if cpu_lines:
    match = re.search(r"([\d.]+)% idle", cpu_lines[-1])
    if match:
        cpu_usage = round(100 - float(match.group(1)), 2)

# Read memory pressure
ram_result = subprocess.run(
    ["memory_pressure"],
    capture_output=True,
    text=True
)

match = re.search(
    r"System-wide (?:memory free|free memory) percentage:\s*(\d+)%",
    ram_result.stdout
)


ram_free = int(match.group(1)) if match else None

# Save to CSV
csv_path = Path(__file__).with_name("monitoring_metrics.csv")
new_file = not csv_path.exists() or csv_path.stat().st_size == 0

with csv_path.open("a", newline="") as file:
    writer = csv.writer(file)

    if new_file:
        writer.writerow(["timestamp", "cpu_usage_percent", "memory_free_percent"])

    writer.writerow([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        cpu_usage,
        ram_free
    ])

print("CPU Usage:", cpu_usage, "%")
print("Memory Free:", ram_free, "%")
print("Monitoring metrics saved!")

#Block 5 - Automatic Monitoring

import time
import subprocess
import re
import csv
from datetime import datetime
from pathlib import Path

csv_path = Path(__file__).with_name("monitoring_metrics.csv")

for i in range(10):
    # Measure CPU
    cpu_result = subprocess.run(
        ["top", "-l", "2", "-n", "0"],
        capture_output=True,
        text=True
    )

    cpu_lines = [
        line for line in cpu_result.stdout.splitlines()
        if "CPU usage:" in line
    ]

    cpu_usage = None

    if cpu_lines:
        match = re.search(r"([\d.]+)% idle", cpu_lines[-1])
        if match:
            cpu_usage = round(100 - float(match.group(1)), 2)

    # Measure memory
    ram_result = subprocess.run(
        ["memory_pressure"],
        capture_output=True,
        text=True
    )

    match = re.search(
        r"System-wide (?:memory free|free memory) percentage:\s*(\d+)%",
        ram_result.stdout
    )

    ram_free = int(match.group(1)) if match else None

    # Save measurement
    with csv_path.open("a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            cpu_usage,
            ram_free
        ])

    print(f"Measurement {i + 1}: CPU={cpu_usage}%, Memory Free={ram_free}%")

    if i < 9:
        time.sleep(5)

print("Automatic monitoring completed!")


#Block 6 - Monitoring Visualization

import csv
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path

csv_path = Path(__file__).with_name("monitoring_metrics.csv")

times = []
cpu_values = []
memory_values = []

with csv_path.open("r", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        if not row["cpu_usage_percent"] or not row["memory_free_percent"]:
            continue

        times.append(datetime.strptime(
            row["timestamp"], "%Y-%m-%d %H:%M:%S"
        ))
        cpu_values.append(float(row["cpu_usage_percent"]))
        memory_values.append(float(row["memory_free_percent"]))

plt.figure(figsize=(10, 5))

plt.plot(times, cpu_values, label="CPU Usage (%)")
plt.plot(times, memory_values, label="Memory Free (%)")

plt.xlabel("Time")
plt.ylabel("Percentage (%)")
plt.title("Drone Monitoring - MacBook Prototype")
plt.legend()
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()

plt.show()
