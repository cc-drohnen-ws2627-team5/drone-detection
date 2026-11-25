# Task 3 progress

## Starting point

Baseline `98b62f9` on `origin/task3-backend` contained standalone Mosquitto, PostgreSQL and MinIO services, a prototype ingestion script and separate smoke scripts. The prior project log recorded a 50-event local burst with matching database and object counts. That run used the prototype and remains separate from the acceptance checks below.

After fetching the repository, Task 1 and Task 2 had only the initial repository files. Task 4 collected Raspberry Pi infrastructure metrics and had its own dashboard; no backend detection feed was defined in its configuration. The existing Task 3 MQTT topic and required fields therefore form the compatibility baseline.

## Delivered on the development branch

- Containerized ingestion and FastAPI, idempotent migration of existing rows, and read endpoints by numeric ID or event UUID.
- TLS, topic-level MQTT ACLs, bearer-authenticated API and metrics, bounded JSON and media, and credentials from configuration.
- Persistent MQTT session with manual acknowledgement after storage, UUID-based deduplication and stable media keys.
- Detection dashboard, filters, pagination, JPEG and MP4 delivery, health checks and Prometheus readiness metric.
- SSD override, cluster stack with two API replicas and rescheduled ingestion, and deployment instructions for Task 1, Task 2 and Task 4.

See [deployment and integration](README.md) for the reliability boundaries and cluster acceptance procedure.

## Local verification

Environment: Windows with Docker Desktop 29.9.2, Linux amd64 containers.

| Check | Observed result |
| --- | --- |
| Application image and broker bootstrap shell syntax | Passed. |
| Compose configuration, SSD override and Swarm stack | Docker CLI configuration validation passed. MinIO image index contains linux/amd64 and linux/arm64. |
| Python unit tests | Four passed, covering input/media validation, legacy identity and MQTT acknowledgement behavior. |
| Compose integration tests | Two passed, covering MQTT over TLS, PostgreSQL migration and legacy lookup, duplicate suppression, API authorization and pagination, JPEG/MP4 byte retrieval, and Prometheus readiness. The full unittest run took 8.627 seconds. |
| 50-event smoke load | All 50 snapshot events appeared exactly once in the API. The last event and count were verified in 1.10 seconds in this local run with tiny test media. |
| MinIO outage | Confirmed a storage error left the event unacknowledged. After MinIO restarted, the same event was redelivered and persisted. |

The local environment did not include the team's Raspberry Pi cluster, SSD or live Task 1/2 producers. A multi-node failover exercise, physical SSD mount test, real-media throughput measurements and live Task 4 notification wiring remain hardware or team integration checks.
