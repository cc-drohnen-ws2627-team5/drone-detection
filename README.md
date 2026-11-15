# drone-detection

## Task 4 – Monitoring, Fault Tolerance, and Evaluation

### 1. Objective

Develop a monitoring solution for the complete drone detection infrastructure, including the sensor node, backend, and Raspberry Pi cluster.

The system should visualize operational data, detect infrastructure failures, provide Telegram notifications, and support experimental evaluation.

### 2. Monitoring Architecture

**Monitoring Stack**
- Prometheus – Metrics collection and alert rule evaluation
- Node Exporter – System resource monitoring
- Grafana Cloud – Monitoring dashboards and visualization
- Telegram Bot – Infrastructure health and drone detection notifications (planned)

**Infrastructure**
- Master: Raspberry Pi 4
- Workers: 8 × Raspberry Pi 3
- Sensor Node and Backend: Integration pending

See [Monitoring Setup and Architecture](MONITORING_SETUP.md) for the architecture diagram and deployment plan.

### 3. Dashboard Requirements

The dashboard should display:

- [ ] Drone detections and confidence values
- [ ] Images, video clips, and tracking information
- [ ] Sensor node and cluster status
- [ ] CPU and RAM utilization (demo prepared)
- [ ] Temperature
- [ ] Network traffic
- [ ] Storage utilization
- [ ] End-to-end latency

### 4. Fault Tolerance

The monitoring system should detect and demonstrate:

- [ ] Cluster node failure
- [ ] Network connection interruption
- [ ] Sensor node restart
- [ ] Camera failure
- [ ] Backend service failure
- [ ] Storage unavailability

### 5. Telegram Notifications

The Telegram Bot should notify team members about:

- [ ] Infrastructure health events
- [ ] Cluster or service failures
- [ ] Drone detection events

### 6. Experimental Evaluation

The complete system must be evaluated experimentally.

Planned activities:

- [ ] Monitor resource utilization during cluster operation
- [ ] Test failure detection and recovery
- [ ] Measure and analyze network traffic
- [ ] Measure end-to-end latency
- [ ] Investigate network traffic and maximum backend processing throughput
- [ ] Document and analyze experimental results

### 7. Current Progress

**Completed – Preparation**
- [x] Initial Python monitoring prototype (`Drone_Monitoring.py`)
- [x] Grafana CPU monitoring dashboard with simulated data
- [x] Prometheus configuration for 9 Raspberry Pis
- [x] Initial Raspberry Pi offline alert rule
- [x] Monitoring architecture diagram
- [x] Monitoring setup documentation

**Pending – Deployment and Integration**
- [ ] Deploy Node Exporter and Prometheus
- [ ] Connect live Raspberry Pi metrics to Grafana
- [ ] Integrate sensor node, backend, and detection data
- [ ] Complete monitoring dashboard
- [ ] Configure Telegram notifications
- [ ] Perform failure simulations
- [ ] Complete experimental evaluation

### 8. Project Files

- [Monitoring Setup and Architecture](MONITORING_SETUP.md)
- [Python Monitoring Prototype](Drone_Monitoring.py)
- [Prometheus Configuration](prometheus.yml)
- [Alert Rules](alerts.yml)

### 9. Current Status

The initial monitoring architecture, configuration files, and Grafana CPU demo have been prepared.

The Grafana dashboard currently uses simulated data. Real monitoring, Telegram notifications, fault tolerance experiments, and performance evaluation are pending deployment and integration with the other project components.hboard uses simulated data, not live measurements.
  
