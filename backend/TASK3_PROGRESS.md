# Task 3: Distributed Backend & Communication Infrastructure

**Project:** Edge-to-Cloud Drone Detection System  
**Module:** Cloud Computing (Master in High Integrity Systems, FraUAS)  
**Branch:** `feature/task3-backend-communication`  
**Status:** Live Working Document (Updated: Week 2)  

---

## 1. Scope & System Architecture

Task 3 serves as the central communication, ingestion, and persistence backbone connecting field-deployed edge camera nodes (the Raspberry Pi cluster) with downstream monitoring dashboards and consumer APIs.

```text
[ Edge Nodes (RPi + YOLO) ]
           │
           │ MQTT (Port 1883 / JSON Telemetry)
           ▼
[ Mosquitto Broker ] ──► [ Ingestion Worker (listener.py) ]
                               │                  │
           ┌───────────────────┴──┐            ┌──┴──────────────────┐
           ▼                      ▼            ▼                     ▼
    [ PostgreSQL 16 ]       [ MinIO (S3) ]   [ FastAPI Service ]  [ Web Dashboard ]
   (Structured Telemetry)  (Raw Frame Snapshots) (REST Endpoints)  (Alert Monitoring)
```

### Core Technology Stack
* **Containerization:** Docker & Docker Compose (isolated, reproducible local runtime)
* **Message Broker:** Eclipse Mosquitto 2.x (MQTT over TCP, default port `1883`)
* **Ingestion Layer:** Python 3 (`paho-mqtt`, `psycopg2-binary`)
* **Relational Database:** PostgreSQL 16 (persistent named volume storage)
* **Object Storage:** MinIO S3-compatible store (for binary drone frame snapshots)
* **REST API:** FastAPI & Uvicorn (OpenAPI/Swagger endpoints for consumers)
* **Target Platforms:** `linux/amd64` (development workstations) & `linux/arm64` (Raspberry Pi cluster)

---

## 2. Completed Milestones

### 2.1 Workspace & Development Environment
- [x] Initialized dedicated local Linux workspace with non-root Docker daemon access.
- [x] Established project directory hierarchy separating broker configuration, database migrations, and Python services.
- [x] Initialized isolated Python virtual environment (`venv`) for local service drivers.

### 2.2 Git & Version Control Initialization
- [x] Cloned organization repository from GitHub.
- [x] Created and checked out working branch: `feature/task3-backend-communication`.
- [x] Configured Git ignoring for container data volumes, virtual environments, and transient caches.

### 2.3 MQTT Broker Infrastructure (`mosquitto`)
- [x] Deployed containerized **Eclipse Mosquitto 2.x** via Docker Compose.
- [x] Configured `mosquitto/config/mosquitto.conf` for local anonymous binding on port `1883`.
- [x] Verified network listener availability and inter-process container routing.

### 2.4 Ingestion Listener Prototype (`listener.py`)
- [x] Developed standalone ingestion client using `paho-mqtt`.
- [x] Implemented subscription handler targeting topic `drones/alerts`.
- [x] Verified complete end-to-end event flow: successfully intercepted simulated edge alert payloads, deserialized JSON attributes (`drone_id`, `confidence`, `status`), and logged structured alerts in real time.

### 2.5 Relational Database Infrastructure (`postgres`)
- [x] Defined the relational schema in the `postgres/init.sql` initialization script with the `detections` table (`id`, `drone_id`, `confidence`, `status`, `image_url`, `detected_at`) and B-tree indexes on the `drone_id` and `detected_at` columns.
- [x] Configured the containerized **PostgreSQL 16** service (`postgres_db`) in the `docker-compose.yml` file exposing port `5432` and attaching the `postgres_data` persistent named volume to `/var/lib/postgresql/data`.
- [x] Configured automated database provisioning by mounting the `init.sql` script into the container directory `/docker-entrypoint-initdb.d/init.sql:ro`.
- [x] Verified the container deployment and confirmed the schema structure directly inside the running database using the `psql` command-line tool.
- [x] Configured an isolated Python virtual environment at `~/.venvs/drone-detection` on the native Linux filesystem to accommodate POSIX symlink requirements.
- [x] Installed the `psycopg2-binary` driver and developed the connectivity verification script `scripts/db_test.py`.
- [x] Validated the Python-to-PostgreSQL pipeline by executing an insert transaction for a simulated detection record and successfully querying the committed record back from the database.

### 2.6 Object Storage Infrastructure (`minio`)
- [x] Configured containerized **MinIO S3** object store (`minio_s3`) using the multi-arch community image `gergito/minio:latest` supporting both `linux/amd64` and `linux/arm64` (Raspberry Pi target deployment).
- [x] Exposed S3 API port `9000` and Web Console port `9001`, bound to persistent volume `minio_data` mounted at `/data`.
- [x] Configured root administrative credentials (`minioadmin` / `minioadmin`).
- [x] Installed the official `minio` Python SDK in the project virtual environment.
- [x] Authored `scripts/s3_test.py` to automate bucket verification (`drone-snapshots`), binary image payload streaming, object persistence (`test_frame.jpg`), and metadata querying.
- [x] Validated bucket contents and object integrity through both automated test output and the MinIO Web Console interface at `http://localhost:9001`.
