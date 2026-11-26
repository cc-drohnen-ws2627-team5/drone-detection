# Task 4 – Monitoring, Fault Tolerance, and Evaluation

## Project: Drone Detection Infrastructure

**Status:** Infrastructure monitoring implemented;
backend integration and final validation pending.

**Last updated:** 26 November 2026

---

## 1. Objective

The objective of Task 4 is to develop a monitoring,
notification, fault tolerance, and evaluation solution
for the complete drone detection infrastructure.

The monitoring solution covers:

- Raspberry Pi cluster availability
- CPU utilization
- Memory utilization
- CPU temperature
- Network traffic
- Storage utilization
- Backend service availability
- Sensor and camera status
- Drone detection events
- Detection confidence
- Images and video clips
- Tracking information
- End-to-end latency
- Backend processing throughput
- Telegram notifications
- Fault tolerance evaluation

The implementation is divided into infrastructure
monitoring and application monitoring.

## 2. System Architecture

### 2.1 Hardware Infrastructure

| Component | Configuration |
|---|---|
| Master Node | Raspberry Pi 4 |
| Worker Nodes | 8 Raspberry Pi 3 |
| Total Cluster Nodes | 9 |
| Sensor Node | Raspberry Pi 5 |
| Network | Ethernet switch and router |
| Monitoring Platform | Grafana Cloud |
| Notification Platform | Telegram |

The sensor node is separate from the nine-node
computing cluster.

### 2.2 Infrastructure Monitoring Architecture

    Raspberry Pi Master + Workers 1-8
                    |
              Node Exporter
                    |
               Prometheus
              (Master Node)
                    |
              Remote Write
                    |
              Grafana Cloud
                    |
          Dashboard and Alerting
                    |
              Telegram Bot

Node Exporter provides hardware and operating
system metrics.

Prometheus collects metrics from all nine nodes
at a scrape interval of 15 seconds.

Selected metrics are transmitted to Grafana Cloud
using Prometheus Remote Write.

Grafana provides visualization, alert evaluation,
and Telegram notification routing.

### 2.3 Application Monitoring Architecture

    Sensor and AI Detection
                    |
                MQTT Broker
                    |
              Ingestion Worker
                    |
          PostgreSQL and MinIO
                    |
                 FastAPI
                /       \
       Prometheus       REST API
            |               |
      Grafana Cloud    Detection Notifier
                            |
                         Telegram

This architecture represents the planned
integration with Task 3.

Live application monitoring integration
has not yet been validated.

## 3. Infrastructure Monitoring Metrics

| Metric | Prometheus Data Source |
|---|---|
| Node Availability | up |
| CPU Usage | node_cpu_seconds_total |
| Memory Usage | node_memory_MemAvailable_bytes, node_memory_MemTotal_bytes |
| Temperature | node_thermal_zone_temp |
| Network RX | node_network_receive_bytes_total |
| Network TX | node_network_transmit_bytes_total |
| Storage Usage | node_filesystem_avail_bytes, node_filesystem_size_bytes |

### 3.1 Node Availability

    up{job="node"}

Interpretation:

- 1: Prometheus successfully scrapes the node.
- 0: Prometheus cannot scrape the node.
- Missing data: No current metric is available.

An unsuccessful scrape does not necessarily mean
that the physical Raspberry Pi is powered off.

### 3.2 CPU Utilization

    100 * (
      1 - avg by (instance) (
        rate(node_cpu_seconds_total{
          job="node",
          mode="idle"
        }[5m])
      )
    )

### 3.3 Memory Utilization

    100 * (
      1 - (
        node_memory_MemAvailable_bytes{job="node"}
        /
        node_memory_MemTotal_bytes{job="node"}
      )
    )

### 3.4 CPU Temperature

    max by (instance) (
      node_thermal_zone_temp{job="node"}
    )

### 3.5 Network Receive Rate

    sum by (instance) (
      rate(node_network_receive_bytes_total{
        job="node",
        device!="lo"
      }[5m])
    )

### 3.6 Network Transmit Rate

    sum by (instance) (
      rate(node_network_transmit_bytes_total{
        job="node",
        device!="lo"
      }[5m])
    )

Network traffic is measured in bytes per second.

Interface-specific queries are required when
evaluating Ethernet bandwidth utilization.

The final RX and TX dashboard query validation
is pending.

### 3.7 Storage Utilization

    100 * (
      1 - (
        node_filesystem_avail_bytes{
          job="node",
          mountpoint="/"
        }
        /
        node_filesystem_size_bytes{
          job="node",
          mountpoint="/"
        }
      )
    )

This metric represents storage utilization
based on available filesystem space.

It may differ from the percentage reported
by the Linux df command.

## 4. Grafana Dashboards

Two separate dashboards have been created
in the Drone Detection folder.

### 4.1 Drone Detection – System Monitoring

The infrastructure dashboard contains:

- Cluster and node availability
- CPU utilization
- Memory utilization
- CPU temperature
- Network receive traffic
- Network transmit traffic
- Storage utilization

Infrastructure metrics have been received
from the Raspberry Pi cluster.

Final visualization and missing-data behavior
will be reviewed before project completion.

### 4.2 Drone Detection – Application Monitoring

The application dashboard has been created
for the planned Task 3 integration.

The following application information is required:

| Information | Planned Source | Status |
|---|---|---|
| Detection Count | Backend REST API or additional metric | Pending |
| Detection History | Backend REST API | Pending |
| Detection Confidence | Backend REST API | Pending |
| Detection Images | Backend Media API | Pending |
| Video Clips | Backend Media API | Pending |
| Tracking Information | Backend REST API and metadata | Partial source support |
| Sensor Status | Sensor heartbeat or exporter | Metric required |
| Camera Status | Camera health check | Metric required |
| Backend Availability | Prometheus up | Integration pending |
| Backend Readiness | drone_backend_ready | Integration pending |
| Storage Availability | Backend health check | Additional check required |
| End-to-End Latency | Evaluation script or additional metric | Script prepared |
| Backend Throughput | Evaluation script or additional metric | Script prepared |
| Failed Events | Ingestion logs or additional metric | Metric required |

Task 3 already provides a web dashboard for
detection information and media retrieval.

The final visualization solution may combine
the Task 3 web dashboard with Grafana monitoring.

The integration approach requires team agreement.

## 5. Alerting and Telegram Notifications

### 5.1 Infrastructure Alert Rules

Six infrastructure alert rules have been
configured in Grafana Cloud.

| Alert Name | Trigger Condition |
|---|---|
| NodeDown | Node scrape status below 1 |
| MissingNodeData | Number of node series below 9 |
| HighTemperature | Temperature above 70 degrees Celsius |
| HighCPUUsage | CPU utilization above 90% |
| HighMemoryUsage | Memory utilization above 85% |
| LowDiskSpace | Storage utilization above 85% |

The MissingNodeData expression is:

    count(up{job="node"}) or vector(0)

This expression counts available node status
series, including series with a value of zero.

It complements NodeDown but does not identify
which node has missing data.

Final validation of pending periods, notification
routing, and No Data behavior is required.

### 5.2 Infrastructure Telegram Notifications

Grafana Alerting is connected to the project
Telegram notification channel.

Telegram notification delivery has been
demonstrated during infrastructure testing.

Automatic node failure and recovery
notifications have been observed.

Not all alert rules and failure scenarios
have been validated individually.

### 5.3 Drone Detection Notifications

A Python notification script has been prepared:

    backend/scripts/telegram_notifier.py

The script is designed to:

- Poll the authenticated backend REST API.
- Identify newly stored detection events.
- Send detection information to Telegram.
- Maintain a persistent event checkpoint.
- Filter simulated performance test events.
- Avoid exposing credentials in logs.

The script requires live integration testing.

The checkpoint mechanism reduces duplicate
notifications but does not guarantee exactly-once
Telegram delivery.

### 5.4 Credential Management

The following configuration values must be
provided securely during deployment:

- BACKEND_API_URL
- API_TOKEN
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

Passwords, tokens, and private infrastructure
addresses must not be committed to GitHub.

## 6. Fault Tolerance Evaluation

### 6.1 Infrastructure Tests

The Raspberry Pi infrastructure has been
evaluated using controlled failure scenarios.

The following measurements were collected
during individual test runs.

| Test Scenario | Observed Result |
|---|---|
| Worker 8 power interruption | Failure detected after 46 seconds |
| Worker 8 power recovery | Recovery observed 61 seconds after reconnecting power |
| Short network interruption | Failure detected after 23 seconds |
| Short network recovery | Recovery observed 15 seconds after reconnecting |
| Extended network interruption | Failure detected after 85 seconds |
| Extended network recovery | Recovery observed 20 seconds after reconnecting |
| Extended network Telegram alert | Notification observed after 120 seconds |
| Worker 3 Node Exporter failure | Failure detected after 25 seconds |
| Prometheus service interruption | Missing node series observed after approximately 90 seconds |

The measured values are observations from
individual experiments, not guaranteed
detection or recovery times.

A Telegram notification was not received
during the Worker 3 exporter failure test.

During the Prometheus interruption test,
no Telegram notification was observed
within the first 300 seconds.

These cases require further investigation.

The Prometheus interruption test represents
a monitoring service failure, not a complete
physical master node failure.

### 6.2 Resource Monitoring Tests

| Test | Observed Result |
|---|---|
| Worker 8 CPU Load | Approximately 1.7% to 26.2% |
| Worker 8 RAM Load | Approximately 30.9% to 52.2% |
| Worker 8 Temperature | Approximately 41.3 to 47.2 degrees Celsius |
| Worker 8 Storage | Approximately 25.5% in Grafana |
| Worker 8 Network Connectivity | 120 ping packets, 0% packet loss |
| Average Ping RTT | Approximately 0.727 ms |

These experiments demonstrate that the
monitoring system can observe changes in
resource utilization.

They do not establish maximum backend
processing capacity.

The high-temperature alert has not yet
been experimentally triggered.

### 6.3 Planned Application Failure Tests

| Test ID | Scenario | Status |
|---|---|---|
| T20 | Sensor Node Restart | Not tested |
| T21 | Sensor Node Recovery | Not tested |
| T22 | Camera Failure | Not tested |
| T23 | Camera Recovery | Not tested |
| T24 | Backend Service Failure | Not tested |
| T25 | Backend Service Recovery | Not tested |
| T26 | Storage Unavailable | Not tested in Task 4 |
| T27 | Storage Recovery | Not tested in Task 4 |

The tests will be performed in coordination
with the responsible team members.

Task 3 has separately reported local storage
failure and recovery testing.

Task 4 monitoring and notification behavior
during these failures remains to be evaluated.

### 6.4 Failure Evaluation Method

For each failure scenario, record:

- T0: Failure introduced.
- T1: Failure detected.
- T2: Telegram notification received.
- T3: Recovery action initiated.
- T4: Service recovery observed.

Calculate:

    Detection Delay = T1 - T0

    Notification Delay = T2 - T0

    Recovery Time = T4 - T3

Missing notifications and unsuccessful
recoveries must also be documented.

## 7. Task 3 Backend Integration

### 7.1 Backend Components

Task 3 provides the following backend components:

- Mosquitto MQTT Broker
- Ingestion Worker
- PostgreSQL Database
- MinIO Object Storage
- FastAPI REST API
- Web Dashboard

### 7.2 Available API Endpoints

| Endpoint | Purpose |
|---|---|
| /health/live | API process availability |
| /health/ready | Backend dependency readiness |
| /metrics | Prometheus metrics |
| /api/v1/detections | Detection event list |
| /api/v1/detections/{id} | Individual detection event |
| /api/v1/detections/{id}/image | Detection image |
| /api/v1/detections/{id}/video | Detection video |

Detection and metrics endpoints require
appropriate API authentication.

### 7.3 Backend Monitoring Metrics

The Task 3 backend currently provides:

    drone_backend_ready

Prometheus will additionally generate:

    up{job="drone-backend"}

The readiness metric indicates combined
PostgreSQL and object storage availability.

It does not independently identify which
backend dependency has failed.

Additional metrics or health checks are
required for individual service monitoring.

### 7.4 Prometheus Integration

The following example configuration
has been prepared:

    prometheus-backend.example.yml

The configuration includes:

- Backend scrape job
- Metrics endpoint
- Bearer token authentication
- HTTPS deployment example
- Grafana Cloud integration requirements

The actual backend hostname, port, protocol,
and authentication configuration must be
confirmed with Task 3.

The existing Prometheus configuration must
be extended rather than replaced.

The Remote Write metric filter must also
include the backend readiness metric.

Live deployment is pending.

## 8. Task 5 Integration

Task 5 provides hardware and distributed
computing benchmark results.

| Measurement | Result |
|---|---|
| Raspberry Pi 3 Ethernet Bandwidth | 94 Mbit/s |
| HPL Performance - 1 Worker | 5.219 GFLOPS |
| HPL Performance - 2 Workers | 7.324 GFLOPS |
| HPL Performance - 4 Workers | 11.895 GFLOPS |
| HPL Performance - 8 Workers | 19.597 GFLOPS |
| HPL Speedup - 8 Workers | 3.75 |
| Temperature Without Cooling | Above 80 degrees Celsius |
| Maximum Temperature With Cooling | 62 degrees Celsius |

These results support the selection of
monitoring metrics and preventive alerts.

They also provide reference values for
network and resource bottleneck analysis.

The detailed integration is documented in:

    TASK5_INTEGRATION.md

Task 5 benchmark results must not be
interpreted as backend processing throughput.

## 9. Backend Performance Evaluation

### 9.1 Throughput Evaluation

A performance evaluation script has been
prepared:

    backend/scripts/performance_test.py

The script is designed to generate simulated
detection events and verify stored events
through the backend REST API.

The planned workload levels are:

| Test ID | Target Rate | Duration | Target Events |
|---|---|---|---|
| PT01 | 1 event/s | 60 s | 60 |
| PT02 | 5 events/s | 60 s | 300 |
| PT03 | 10 events/s | 60 s | 600 |
| PT04 | 25 events/s | 60 s | 1500 |
| PT05 | 50 events/s | 60 s | 3000 |
| PT06 | 100 events/s | 60 s | 6000 |

The actual publishing rate must be measured
because it may differ from the target rate.

The evaluation must distinguish between:

- Target events
- Attempted events
- MQTT-acknowledged events
- Successfully stored events
- Events not verified within the test period

An MQTT acknowledgement does not guarantee
successful database or object storage persistence.

### 9.2 Throughput Calculation

    Verified Throughput =
    Verified Stored Events / Total Observation Time

    Success Rate (%) =
    Verified Stored Events / Attempted Events * 100

The current script includes connection,
publishing, and API verification time.

Its output is therefore an observed
end-to-end throughput measurement.

A separate processing-time measurement
may be required to determine pure backend
processing capacity.

Maximum sustainable backend throughput
has not yet been established.

### 9.3 Latency Evaluation

The following script has been prepared:

    backend/scripts/latency_test.py

The script measures the observed duration
between simulated detection generation
and successful API retrieval.

The planned evaluation includes:

- Minimum latency
- Average latency
- Median latency
- P95 latency
- Maximum latency
- Successful samples
- Failed samples

The script exports summary and individual
sample measurements as CSV files.

The current method includes MQTT publishing,
backend processing, and API polling delay.

It does not include real camera acquisition
or AI inference time.

Complete sensor-to-backend latency evaluation
requires integration with the actual sensor.

### 9.4 Network Traffic Evaluation

Network receive and transmit rates will be
recorded during backend load tests.

Task 5 measured a reference Ethernet
bandwidth of 94 Mbit/s on Raspberry Pi 3.

    Network Utilization (%) =
    Traffic (B/s) * 8 / 94000000 * 100

The calculation must be performed separately
for receive and transmit traffic on the
relevant Raspberry Pi 3 Ethernet interface.

Background traffic and payload size must
be considered when interpreting results.

### 9.5 Experimental Conditions

The following conditions should be recorded
for reproducible backend evaluation:

- Backend deployment configuration
- Number of active nodes
- Actual input rate
- Test duration
- Image and video payload sizes
- CPU and memory utilization
- Network utilization
- CPU temperature
- Storage utilization
- Error and timeout counts

The performance and latency scripts are
prepared but have not yet been tested
against the live Task 3 backend.

## 10. Robustness and Single Points of Failure

The monitoring architecture currently uses
a centralized Prometheus instance running
on the master node.

Grafana Cloud provides external monitoring
visualization and alert evaluation.

However, the following potential single
points of failure remain:

| Component | Potential Impact |
|---|---|
| Master Node | Loss of centralized metric collection |
| Prometheus Service | Interruption of monitoring data |
| Network Switch | Loss of cluster communication |
| Router or Internet | Interruption of cloud metric transmission |
| Grafana Cloud | Loss of cloud visualization or alert evaluation |
| MQTT Broker | Interruption of event ingestion |
| PostgreSQL | Interruption of metadata storage |
| MinIO | Interruption of media storage |
| Telegram Notifier | Interruption of detection notifications |

Possible improvements include:

- Persistent monitoring service configuration
- Automatic service restart
- Independent monitoring heartbeat
- Redundant backend service deployment
- Persistent event storage
- Reliable notification checkpoints
- Explicit missing-data alerts

These improvements require further
implementation or validation.

Grafana Cloud alone does not eliminate
the master node as a monitoring single
point of failure.

## 11. Current Implementation Status

| Component | Status |
|---|---|
| Raspberry Pi Cluster Monitoring | Implemented and partially validated |
| Prometheus | Implemented |
| Grafana Cloud Remote Write | Implemented and observed |
| System Monitoring Dashboard | Implemented |
| Application Monitoring Dashboard | Initial setup |
| Infrastructure Alert Rules | Configured |
| Infrastructure Telegram Notifications | Partially validated |
| Raspberry Pi Fault Tests | Partially completed |
| Backend Prometheus Configuration | Prepared |
| Backend Performance Script | Prepared, not tested |
| Backend Latency Script | Prepared, not tested |
| Telegram Detection Script | Prepared, not tested |
| Task 5 Integration | Documented |
| Sensor and Camera Monitoring | Pending |
| Backend Fault Tolerance Evaluation | Pending |
| Maximum Backend Throughput | Pending |
| Complete End-to-End Latency | Pending |
| Final System Validation | Pending |

## 12. Remaining Tasks

### 12.1 Raspberry Pi Validation

- Verify all nine nodes after restart.
- Verify Prometheus and Node Exporter services.
- Validate all dashboard queries.
- Review missing-data visualization.
- Verify alert thresholds and pending periods.
- Validate Telegram notification routing.
- Investigate missing failure notifications.
- Validate Prometheus failure detection.
- Test internet disconnection and recovery.
- Verify Remote Write stability.

### 12.2 Task 3 Integration

- Confirm backend deployment location.
- Obtain authorized API access.
- Configure backend metrics scraping.
- Extend the Remote Write metric allowlist.
- Connect application monitoring data.
- Validate backend health alerts.
- Test the Telegram detection notifier.
- Review and test the performance scripts.
- Evaluate backend throughput and latency.
- Perform backend and storage failure tests.

### 12.3 Sensor Integration

- Obtain sensor and camera health information.
- Monitor sensor availability.
- Monitor camera availability.
- Test sensor restart and recovery.
- Test camera failure and recovery.
- Evaluate complete sensor-to-backend latency.

### 12.4 Final Documentation

- Update experimental results.
- Add Grafana screenshots.
- Add Telegram notification evidence.
- Include raw measurement files.
- Document remaining limitations.
- Provide reproducible deployment instructions.
- Prepare the final project demonstration.

## 13. Documentation and Repository Files

| File | Purpose |
|---|---|
| README.md | Project overview |
| MONITORING_SETUP.md | Monitoring setup instructions |
| prometheus.yml | Prometheus configuration |
| alerts.yml | Alert configuration reference |
| Drone_Monitoring.py | Initial monitoring prototype |
| prometheus-backend.example.yml | Backend scrape configuration example |
| backend/scripts/performance_test.py | Backend throughput evaluation |
| backend/scripts/latency_test.py | Backend latency evaluation |
| backend/scripts/telegram_notifier.py | Detection notification service |
| TASK5_INTEGRATION.md | Task 5 benchmark integration |
| TASK4_DOCUMENTATION.md | Task 4 implementation and evaluation status |

Additional monitoring specifications,
test results, and experimental evidence
are maintained in Google Sheets.

## 14. Conclusion

Task 4 has established an infrastructure
monitoring solution for the Raspberry Pi cluster.

Prometheus, Grafana Cloud, and Telegram
provide the foundation for resource monitoring,
visualization, and failure notification.

Initial experiments demonstrate infrastructure
monitoring and selected failure detection
capabilities.

Backend integration configurations and
evaluation scripts have been prepared.

The complete Task 4 requirements cannot
be considered fulfilled until backend,
sensor, camera, and application monitoring
have been integrated and experimentally
validated.

## 15. AI Assistance

ChatGPT was used to assist with:

- Monitoring architecture planning
- Prometheus query preparation
- Grafana configuration guidance
- Python monitoring and evaluation scripts
- Experimental evaluation design
- Documentation preparation

Experimental observations are based on
recorded project measurements.

AI-assisted code and configuration require
technical review and integration testing.

Task 5 benchmark results are attributed
to the responsible Task 5 team member.

This document represents the current
implementation status and will be updated
after final system integration.
