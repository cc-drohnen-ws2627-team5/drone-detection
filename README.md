# Drone Detection Infrastructure

## Task 4 – Monitoring, Fault Tolerance, and Evaluation

### 1. Overview

Task 4 develops a monitoring, alerting, fault tolerance,
and experimental evaluation solution for the complete
drone detection infrastructure.

The solution combines Prometheus, Node Exporter,
Grafana Cloud, and Telegram notifications.

Infrastructure monitoring has been implemented and
partially validated using the Raspberry Pi cluster.

Backend and sensor integration, application monitoring,
and final experimental evaluation are still in progress.

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
- Sensor Node: Raspberry Pi 5
- Backend: Task 3 distributed backend infrastructure

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
for additional architecture and deployment information.

### 3. Monitoring Dashboards

Two Grafana dashboards have been created:

#### System Monitoring

- [x] Cluster and node availability
- [x] CPU utilization
- [x] Memory utilization
- [x] CPU temperature
- [x] Network traffic
- [x] Storage utilization

Live Raspberry Pi metrics have been received.
Final dashboard validation is pending.

#### Application Monitoring

- [x] Initial dashboard setup
- [ ] Drone detection events and confidence
- [ ] Images and video clips
- [ ] Tracking information
- [ ] Sensor and camera status
- [ ] Backend service availability
- [ ] Storage availability
- [ ] End-to-end latency
- [ ] Backend throughput

Application monitoring requires integration
with Task 3 and the sensor infrastructure.

### 4. Alerting and Telegram

Six infrastructure alert rules are configured:

| Alert | Condition |
|---|---|
| NodeDown | Node scrape status below 1 |
| MissingNodeData | Available node series below 9 |
| HighTemperature | Temperature above 70°C |
| HighCPUUsage | CPU usage above 90% |
| HighMemoryUsage | Memory usage above 85% |
| LowDiskSpace | Storage usage above 85% |

Infrastructure Telegram notifications have been
partially validated through failure experiments.

A separate Python notification script has been
prepared for drone detection events.

Live testing of detection notifications is pending.

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

Detailed experimental observations and limitations
are available in the Task 4 documentation.

### 6. Experimental Evaluation

#### Infrastructure Evaluation

- [x] CPU load monitoring
- [x] Memory load monitoring
- [x] Temperature monitoring
- [x] Storage utilization monitoring
- [x] Network connectivity and traffic monitoring
- [x] Selected failure and recovery measurements

#### Backend Evaluation

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

#### Task 3 – Backend and Communication

The planned integration includes:

- Authenticated Prometheus metrics scraping
- Backend service monitoring
- Detection data retrieval through the REST API
- Telegram detection notifications
- Backend performance and latency evaluation
- Backend failure and recovery testing

#### Task 5 – HPL and MPI

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
    |-- monitoring/
    |   |-- prometheus.yml
    |   |-- prometheus-backend.example.yml
    |   |-- alerts.yml
    |   |-- grafana-dashboard.js
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
- [Alert Rules](monitoring/alerts.yml)
- [Grafana Dashboard Reference](monitoring/grafana-dashboard.js)

#### Backend Scripts

- [Performance Test](backend/scripts/performance_test.py)
- [Latency Test](backend/scripts/latency_test.py)
- [Telegram Notifier](backend/scripts/telegram_notifier.py)

#### Prototype

- [Initial Python Monitoring Prototype](prototype/Drone_Monitoring.py)

The prototype was developed for initial local testing
on macOS and is not the production monitoring solution.

### 10. Current Status

| Component | Status |
|---|---|
| Infrastructure Monitoring | Implemented |
| Grafana Cloud | Connected and observed |
| System Monitoring Dashboard | Implemented |
| Application Monitoring Dashboard | Initial setup |
| Infrastructure Alerting | Partially validated |
| Telegram Infrastructure Notifications | Partially validated |
| Backend Integration | Prepared |
| Performance and Latency Scripts | Prepared, not tested |
| Telegram Detection Script | Prepared, not tested |
| Task 5 Integration | Documented |
| Final System Evaluation | Pending |

### 11. Security and Limitations

- Credentials and tokens must not be committed.
- Backend scripts require authorized API and MQTT access.
- Example configurations require deployment-specific values.
- Centralized Prometheus remains a potential single point
  of failure.
- Final configuration and integration validation is required.

### 12. AI Assistance

ChatGPT was used to support monitoring design,
configuration preparation, Python scripting,
experimental planning, and documentation.

AI-assisted implementations require technical
review and experimental validation.

## 13. Documentation and Repository Files

| File | Purpose |
|---|---|
| [README.md](../README.md) | Project overview |
| [MONITORING_SETUP.md](MONITORING_SETUP.md) | Monitoring setup instructions |
| [prometheus.yml](../monitoring/prometheus.yml) | Prometheus configuration |
| [alerts.yml](../monitoring/alerts.yml) | Alert configuration reference |
| [grafana-dashboard.js](../monitoring/grafana-dashboard.js) | Grafana dashboard reference |
| [Drone_Monitoring.py](../prototype/Drone_Monitoring.py) | Initial macOS monitoring prototype |
| [prometheus-backend.example.yml](../monitoring/prometheus-backend.example.yml) | Backend scrape configuration example |
| [performance_test.py](../backend/scripts/performance_test.py) | Backend throughput evaluation |
| [latency_test.py](../backend/scripts/latency_test.py) | Backend latency evaluation |
| [telegram_notifier.py](../backend/scripts/telegram_notifier.py) | Detection notification service |
| [TASK5_INTEGRATION.md](TASK5_INTEGRATION.md) | Task 5 benchmark integration |

Additional monitoring specifications,
test results, and experimental evidence
are maintained in Google Sheets.
---

Last updated: 26 November 2026
