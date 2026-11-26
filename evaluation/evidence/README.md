# Task 4 – Monitoring and Test Evidence

## 1. Overview

This directory contains screenshots collected during the Raspberry Pi cluster monitoring and fault detection experiments.

The monitoring infrastructure consists of one master node and eight worker nodes, using Prometheus, Node Exporter, Grafana Cloud and Telegram notifications.

## 2. System Monitoring

| Metric | Observed Result | Evidence |
|---|---|---|
| Node Status | All 9 nodes online at the selected historical observation | [Screenshot](01-node-status.png) |
| CPU Usage | Peak of approximately 92% | [Screenshot](02-cpu-usage.png) |
| RAM Usage | Master approximately 6%, workers 30–32%, peak approximately 52% | [Screenshot](03-ram-usage.png) |
| CPU Temperature | Mostly 36–45°C, peak approximately 47°C | [Screenshot](04-cpu-temperature.png) |
| Network Traffic | RX and TX visualization for all nine nodes | [Screenshot](05-network-traffic.png) |
| Storage Usage | Master 31%, workers 25–26% | [Screenshot](06-storage-usage.png) |

## 3. Telegram Alerting

| Test | Observed Result | Evidence |
|---|---|---|
| Notification Test | Test notification successfully received | [Screenshot](07-telegram-test.jpg) |
| MissingNodeData – Firing | Only 8 of 9 expected node series available | [Screenshot](08-missing-node-firing.jpg) |
| MissingNodeData – Resolved | All 9 expected node series available again | [Screenshot](09-missing-node-resolved.jpg) |
| NodeDown – Firing | Worker8 monitoring endpoint unreachable | [Screenshot](10-worker8-firing.jpg) |
| NodeDown – Resolved | Worker8 monitoring endpoint reachable again | [Screenshot](11-worker8-resolved.jpg) |

## 4. Fault Detection and Recovery

The experiments demonstrate that the monitoring system can:

- Detect unavailable monitoring endpoints.
- Detect missing monitoring data.
- Send automatic Telegram alerts.
- Detect the restoration of monitoring connectivity.
- Send automatic recovery notifications.

## 5. Limitations

- Screenshot values are approximate.
- Historical screenshots do not represent the current cluster status.
- MissingNodeData measures available monitoring series, not necessarily healthy nodes.
- Recovery notifications currently reuse failure descriptions.
- Exact notification delays require separate timestamp measurements.
- RX and TX query definitions require final verification.
- Fault detection does not demonstrate automatic service failover.
- Backend, sensor, camera and application-level monitoring require further integration and testing.

## 6. Conclusion

The collected evidence demonstrates successful infrastructure monitoring, automatic fault detection and Telegram notification delivery for the Raspberry Pi cluster.

Further experiments are required to evaluate the complete drone detection infrastructure.
