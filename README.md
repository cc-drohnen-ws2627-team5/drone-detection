# drone-detection

## Task 4 – System Monitoring

### Objective
Monitor the health, performance, and availability of the Raspberry Pi cluster used for drone detection.

### Monitoring Stack
- **Node Exporter:** Collects system metrics from Raspberry Pis.
- **Prometheus:** Collects metrics and evaluates alert rules.
- **Grafana Cloud:** Visualizes system performance and status.

### Current Progress
- [x] Python monitoring prototype created
- [x] Grafana CPU dashboard created with simulated data
- [x] Prometheus configuration prepared for 9 Raspberry Pis
- [x] Offline alert rule prepared
- [x] Monitoring architecture and setup documentation created
- [ ] Node Exporter deployed on Raspberry Pis
- [ ] Prometheus connected to live metrics
- [ ] Fault tolerance and alert notifications tested

### Project Files
- [Monitoring Setup and Architecture](MONITORING_SETUP.md)
- [Python Monitoring Prototype](Drone_Monitoring.py)
- [Prometheus Configuration](prometheus.yml)
- [Alert Rules](alerts.yml)

### Current Status
**Preparation completed. Deployment and integration testing are pending access to the Raspberry Pi cluster.**

The current Grafana CPU dashboard uses simulated data, not live measurements.
  
