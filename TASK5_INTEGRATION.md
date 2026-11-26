# Task 4 – Integration of Task 5 Results

## 1. Objective

This document connects the results of Task 5
(High-Performance LINPACK and MPI) with Task 4
(Monitoring, Fault Tolerance, and Evaluation).

The objective is to use existing cluster measurements
to support monitoring decisions, alert thresholds,
resource analysis, and backend performance evaluation.

Task 5 benchmark results are used as reference values.
They do not replace the backend-specific measurements
required by Task 4.

## 2. Cluster Configuration

| Component | Configuration |
|---|---|
| Master Node | Raspberry Pi 4, 8 GB RAM |
| Worker Nodes | 8 Raspberry Pi 3 Model B |
| CPU per Worker | 4 cores, 1.2 GHz |
| Total Worker Cores | 32 |
| Usable RAM per Worker | Approximately 905 MB |
| Network Switch | 24-port Gigabit switch |
| Worker Ethernet | 100 Mbit/s |
| Measured Bandwidth | 94 Mbit/s |
| Operating System | Debian 13, 64-bit |
| Cooling | 120 mm USB fan |

The master node coordinates the MPI workloads
but does not participate in the benchmark computation.

Task 4 monitors the master and all eight worker nodes
using Prometheus, Node Exporter, and Grafana Cloud.

## 3. Network Performance

### 3.1 Task 5 Results

Task 5 measured approximately 94 Mbit/s using iperf3
on the Raspberry Pi 3 Ethernet interface.

Although the network switch supports Gigabit Ethernet,
the Raspberry Pi 3 interfaces are limited to 100 Mbit/s.

This limitation is particularly relevant for
communication-intensive distributed workloads.

### 3.2 Monitoring Metrics

The following Prometheus metrics are used:

- node_network_receive_bytes_total
- node_network_transmit_bytes_total

The corresponding Grafana panels display
network receive and transmit rates in bytes per second.

### 3.3 Network Utilization

The measured bandwidth can be used as a reference
for estimating network utilization.

Network Utilization (%) =
Traffic (B/s) * 8 / 94000000 * 100

The calculation should be performed separately
for receive and transmit traffic on the relevant
Raspberry Pi 3 Ethernet interface.

The measured bandwidth is a reference value,
not a guaranteed maximum under all workloads.

## 4. Thermal Monitoring

### 4.1 Task 5 Results

Task 5 observed thermal throttling above 80 degrees
Celsius during HPL workloads without active cooling.

With a 120 mm USB fan, the maximum measured
temperature was 62 degrees Celsius.

### 4.2 Task 4 Monitoring

CPU temperature is monitored using:

- node_thermal_zone_temp

A preventive temperature alert has been configured
at 70 degrees Celsius.

This threshold provides an early warning before
the temperatures associated with throttling
observed in Task 5 are reached.

The threshold is a Task 4 design decision,
not a mandatory hardware limit.

### 4.3 Additional Monitoring

Temperature alone does not confirm whether
thermal throttling or undervoltage has occurred.

A possible future extension is to collect
Raspberry Pi hardware status using:

    vcgencmd get_throttled

The result could be exposed to Prometheus through
the Node Exporter textfile collector.

This extension has not yet been implemented.

## 5. Resource Monitoring and Alert Thresholds

| Resource | Monitoring Metric | Proposed or Configured Threshold |
|---|---|---|
| Node Availability | up | Below 1 |
| Cluster Data Availability | count(up{job="node"}) or vector(0) | Below 9 |
| CPU Usage | node_cpu_seconds_total | Above 90% |
| Memory Usage | node_memory_MemAvailable_bytes, node_memory_MemTotal_bytes | Above 85% |
| CPU Temperature | node_thermal_zone_temp | Above 70 degrees Celsius |
| Storage Usage | node_filesystem_avail_bytes, node_filesystem_size_bytes | Above 85% |

CPU, memory, and storage utilization are calculated
from the corresponding raw Prometheus metrics.

These thresholds represent the current Task 4
monitoring configuration.

Final validation of alert durations, notification
routing, and missing-data behavior is pending.

## 6. Cluster Scalability

### 6.1 HPL Benchmark Results

| Workers | MPI Processes | Mean GFLOPS | Speedup |
|---|---|---|---|
| 1 | 4 | 5.219 | 1.00 |
| 2 | 8 | 7.324 | 1.40 |
| 4 | 16 | 11.895 | 2.28 |
| 8 | 32 | 19.597 | 3.75 |

The results show that increasing the number
of worker nodes improves computing performance.

However, the measured speedup is lower than
the ideal linear speedup.

### 6.2 Monte Carlo Evaluation

Task 5 reported the following speedup values
with one process per Raspberry Pi:

- 2 Raspberry Pis: 2.00
- 4 Raspberry Pis: 3.95

Within a single Raspberry Pi:

- 2 cores: 1.60
- 4 cores: 2.49

The preliminary Task 5 analysis identifies shared
memory access as a possible limitation within
a single Raspberry Pi.

### 6.3 Matrix Multiplication

Matrix size: 3072 x 3072.

| MPI Processes | Execution Time |
|---|---|
| 1 | 33.1 s |
| 2 | 17.3 s |
| 4 | 17.3 s |
| 8 | 22.6 s |
| 16 | 33.1 s |
| 32 | 33.1 s |

Task 5 identified the 100 Mbit/s Ethernet link
used by rank 0 as a network bottleneck.

Increasing the number of processes does not
necessarily improve performance when communication
overhead becomes significant.

### 6.4 CPU System Overhead

During HPL measurements, the share of CPU time
spent in the operating system kernel increased
from approximately 1% with one worker to 23%
with eight workers.

Task 5 associates this increase with the
network limitations of the cluster.

Task 4 can investigate similar behavior using:

    100 * avg by (instance) (
      rate(node_cpu_seconds_total{
        job="node",
        mode="system"
      }[5m])
    )

This query is proposed for further analysis.
It has not yet been added to the dashboard.

## 7. Monitoring Implications

The Task 5 results support the following
monitoring decisions:

- Monitor all nine Raspberry Pi nodes.
- Monitor CPU and memory utilization.
- Monitor network traffic during distributed workloads.
- Monitor CPU temperature during sustained workloads.
- Investigate network saturation and system CPU overhead.
- Evaluate resource utilization together with throughput.
- Consider additional throttling and undervoltage metrics.

Task 5 also used the absence of throttling
and undervoltage as validity criteria for
its benchmark measurements.

These criteria should be considered when
evaluating backend performance in Task 4.

## 8. Monitoring Limitations

The following limitations remain:

- Thermal throttling is not directly monitored.
- Undervoltage is not directly monitored.
- Network utilization requires interface-specific analysis.
- Task 5 benchmarks do not measure backend event throughput.
- HPL GFLOPS cannot be converted directly into events per second.
- Backend performance depends on MQTT, ingestion,
  database operations, object storage, and media size.
- Backend and sensor integration tests are still pending.

## 9. Future Backend Evaluation

Task 4 will evaluate the backend under different
input rates after integration with Task 3.

Planned input rates:

- 1 event per second
- 5 events per second
- 10 events per second
- 25 events per second
- 50 events per second
- 100 events per second

The following measurements are planned:

- Actual input rate
- MQTT acknowledgements
- Successfully stored events
- Backend throughput
- Event success rate
- Observed end-to-end latency
- CPU utilization
- Memory utilization
- Network receive and transmit rates
- CPU temperature
- Storage utilization

The maximum sustainable backend throughput
will be determined experimentally.

The Task 5 measurements will serve as reference
values when interpreting resource limitations.

## 10. Source

Task 5: High-Performance LINPACK (HPL) and MPI

Owner: Kubilay

Source status: 15 November 2026

Relevant measurement files:

- messungen/CC_T5_Messungen.csv
- messungen/CC_T5_Netzwerk.csv
- messungen/rohdaten/

The source reports completed cluster measurements
and preliminary findings. The final Task 5 analysis
and documentation were still in progress.

## 11. AI Assistance

ChatGPT was used to assist with drafting this
integration document and proposing monitoring
metrics and evaluation methods.

The original benchmark measurements are attributed
to Task 5.

The proposed Task 4 extensions require review
and validation before final deployment.
