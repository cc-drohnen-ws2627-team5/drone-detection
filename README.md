# Drone Detection Infrastructure

## Task 4 – Monitoring, Fault Tolerance, and Evaluation

### 1. Overview

Task 4 develops a monitoring, alerting, fault tolerance,
and experimental evaluation solution for the complete
drone detection infrastructure.

The solution combines Prometheus, Node Exporter,
Grafana Cloud, Telegram notifications, and Python-based
experimental evaluation tools.

Infrastructure monitoring has been implemented and
partially validated using the Raspberry Pi cluster.

Backend integration, sensor monitoring, application
monitoring, and final system evaluation are in progress.

### 2. Monitoring Architecture

| Component | Purpose |
|---|---|
| Prometheus | Metrics collection and remote transmission |
| Node Exporter | Hardware and operating system metrics |
| Grafana Cloud | Visualization and alert evaluation |
| Telegram Bot | Infrastructure and detection notifications |
| Python | Backend evaluation and detection notifications |

#### Infrastructure

- Master: Raspberry Pi 4
- Workers: 8 Raspberry Pi 3
- Sensor Node: Raspberry Pi 5 (integration pending)
- Backend: Task 3 infrastructure (integration pending)

#### Data Flow

    Raspberry Pi Cluster
            |
       Node Exporter
            |
        Prometheus
            |
        Remote Write
            |
        Grafana Cloud
            |
       Telegram Alerts

See [Monitoring Setup](docs/MONITORING_SETUP.md)
for additional deployment information.

### 3. Monitoring Dashboards

#### 3.1 System Monitoring

- [x] Cluster and node availability
- [x] CPU utilization
- [x] Memory utilization
- [x] CPU temperature
- [x] Network traffic visualization
- [x] Storage utilization

Live metrics from nine Raspberry Pi nodes have been
received and visualized in Grafana Cloud.

Final dashboard configuration verification is pending.

[Grafana System Monitoring Dashboard Export](monitoring/grafana/system-monitoring.json)

#### 3.2 Application Monitoring

- [x] Initial dashboard setup
- [ ] Drone detection events
- [ ] Detection confidence
- [ ] Images and video clips
- [ ] Tracking information
- [ ] Sensor status
- [ ] Camera status
- [ ] Backend service availability
- [ ] Storage availability
- [ ] End-to-end latency
- [ ] Backend throughput
- [ ] Failed event monitoring

Application monitoring requires integration with
Task 3 and the sensor infrastructure.

### 4. Alerting and Telegram

Six infrastructure alert rules are configured.

| Alert | Condition | Validation |
|---|---|---|
| NodeDown | Node scrape status below 1 | Tested |
| MissingNodeData | Available node series below 9 | Tested |
| HighTemperature | Temperature above 70°C | Pending |
| HighCPUUsage | CPU usage above 90% | Pending |
| HighMemoryUsage | Memory usage above 85% | Pending |
| LowDiskSpace | Storage usage above 85% | Pending |

The following Telegram notification functions
have been demonstrated:

- Manual notification test
- Automatic infrastructure failure notifications
- Automatic recovery notifications
- Missing monitoring data notifications

A separate Python notification script has been
prepared for drone detection events.

Live testing of detection notifications is pending.

[Grafana Cloud Alert Rules Export](monitoring/grafana/alert-rules.yaml)

### 5. Fault Tolerance

| Failure Scenario | Status |
|---|---|
| Cluster node failure and recovery | Tested |
| Network interruption and recovery | Tested |
| Node Exporter failure | Partially tested |
| Prometheus service failure | Partially tested |
| Internet interruption and recovery | Pending |
| Sensor node restart | Pending |
| Camera failure | Pending |
| Backend service failure | Pending |
| Storage unavailability | Pending |

The experiments demonstrate fault detection and
notification delivery for selected infrastructure
failure scenarios.

Automatic service failover and complete system
fault tolerance have not yet been demonstrated.

Detailed observations and limitations are available
in the Task 4 documentation and experimental evidence.

### 6. Experimental Evaluation

#### 6.1 Infrastructure Evaluation

- [x] CPU load monitoring
- [x] Memory load monitoring
- [x] Temperature monitoring
- [x] Storage utilization monitoring
- [x] Network connectivity and traffic monitoring
- [x] Selected failure and recovery measurements
- [x] Telegram notification verification

#### 6.2 Backend Evaluation

- [x] Performance test script prepared
- [x] Latency test script prepared
- [x] Experimental evaluation plan prepared
- [ ] Backend throughput measurements
- [ ] Maximum sustainable processing throughput
- [ ] Backend network traffic evaluation
- [ ] Complete end-to-end latency measurements

The prepared scripts require integration testing
with the live Task 3 backend.

### 7. Task Integration

#### 7.1 Task 3 – Backend and Communication

The planned integration includes:

- Authenticated Prometheus metrics scraping
- Backend service monitoring
- Detection data retrieval through the REST API
- Telegram detection notifications
- Backend performance and latency evaluation
- Backend failure and recovery testing

The integration configuration and Python scripts
have been prepared but require deployment and
experimental validation.

#### 7.2 Task 5 – HPL and MPI

Task 5 benchmark results provide reference values
for network bandwidth, thermal behavior,
cluster scalability, and resource limitations.

These measurements support Task 4 monitoring
decisions but do not replace backend-specific
performance measurements.

See [Task 5 Integration](docs/TASK5_INTEGRATION.md).

### 8. Repository Structure

    drone-detection/
    |
    |-- backend/
    |   |-- scripts/
    |       |-- performance_test.py
    |       |-- latency_test.py
    |       |-- telegram_notifier.py
    |
    |-- docs/
    |   |-- MONITORING_SETUP.md
    |   |-- TASK4_DOCUMENTATION.md
    |   |-- TASK5_INTEGRATION.md
    |
    |-- evaluation/
    |   |-- Task 4 – Monitoring Metrics.xlsx
    |   |-- evidence/
    |       |-- README.md
    |       |-- Grafana screenshots
    |       |-- Telegram screenshots
    |
    |-- monitoring/
    |   |-- prometheus.yml
    |   |-- prometheus-backend.example.yml
    |   |-- alerts.yml
    |   |-- grafana-dashboard.js
    |   |-- grafana/
    |       |-- system-monitoring.json
    |       |-- alert-rules.yaml
    |
    |-- prototype/
    |   |-- Drone_Monitoring.py
    |
    |-- .gitignore
    |-- README.md

### 9. Documentation and Project Files

#### Documentation

- [Monitoring Setup](docs/MONITORING_SETUP.md)
- [Task 4 Documentation](docs/TASK4_DOCUMENTATION.md)
- [Task 5 Integration](docs/TASK5_INTEGRATION.md)

#### Monitoring Configuration

- [Prometheus Configuration](monitoring/prometheus.yml)
- [Backend Scrape Example](monitoring/prometheus-backend.example.yml)
- [Alert Configuration Reference](monitoring/alerts.yml)
- [Grafana Dashboard Reference](monitoring/grafana-dashboard.js)
- [Grafana Dashboard JSON](monitoring/grafana/system-monitoring.json)
- [Grafana Alert Rules YAML](monitoring/grafana/alert-rules.yaml)

#### Backend Scripts

- [Performance Test](backend/scripts/performance_test.py)
- [Latency Test](backend/scripts/latency_test.py)
- [Telegram Notifier](backend/scripts/telegram_notifier.py)

#### Prototype

- [Initial Python Monitoring Prototype](prototype/Drone_Monitoring.py)

The prototype was developed for initial local testing
on macOS and is not the production monitoring solution.

### 10. Monitoring Artifacts and Experimental Evidence

- [Monitoring and Evaluation Spreadsheet](evaluation/Task%204%20%E2%80%93%20Monitoring%20Metrics.xlsx)
- [Test Evidence and Results](evaluation/evidence/README.md)
- [Grafana and Telegram Screenshots](evaluation/evidence/)

The spreadsheet contains monitoring specifications,
alert rules, architecture information, test results,
backend integration planning, experimental evaluation
planning, and Task 5 benchmark references.

The evidence directory contains historical Grafana
screenshots and Telegram notification screenshots.

The exported Grafana files contain monitoring
configurations, not historical measurement data.

### 11. Current Implementation Status

| Component | Status |
|---|---|
| Infrastructure Monitoring | Implemented |
| Grafana Cloud | Connected and observed |
| System Monitoring Dashboard | Implemented |
| Application Monitoring Dashboard | Initial setup |
| Infrastructure Alerting | Partially validated |
| Telegram Infrastructure Notifications | Partially validated |
| Infrastructure Fault Detection | Partially validated |
| Backend Integration | Prepared |
| Performance and Latency Scripts | Prepared, not tested |
| Telegram Detection Script | Prepared, not tested |
| Task 5 Integration | Documented |
| Experimental Evidence | Documented |
| Final System Evaluation | Pending |

### 12. Security and Limitations

- Credentials and tokens must not be committed.
- Backend scripts require authorized API and MQTT access.
- Example configurations require deployment-specific values.
- Centralized Prometheus remains a potential single point of failure.
- Missing monitoring data does not necessarily indicate that a node is offline.
- Historical screenshots do not represent the current cluster status.
- Final configuration and integration validation is required.
- Fault detection alone does not demonstrate automatic service failover.

### 13. Remaining Tasks

- [ ] Complete Task 3 backend integration
- [ ] Complete application monitoring
- [ ] Integrate sensor and camera monitoring
- [ ] Validate remaining infrastructure alert rules
- [ ] Validate drone detection notifications
- [ ] Complete remaining fault tolerance experiments
- [ ] Evaluate backend network traffic
- [ ] Measure maximum sustainable backend throughput
- [ ] Evaluate end-to-end latency
- [ ] Complete final system validation
- [ ] Prepare final project presentation and demonstration

### 14. AI Assistance

ChatGPT was used to support monitoring design,
configuration preparation, Python scripting,
experimental planning, and documentation.

AI-assisted implementations require technical
review and experimental validation.

---

Last updated: 26 November 2026
