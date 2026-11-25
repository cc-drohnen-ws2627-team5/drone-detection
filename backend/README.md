# Task 3 · Distributed Backend and Communication

The backend connects the Raspberry Pi sensor and detection pipeline to the dashboard and monitoring.

| Component | Role |
| --- | --- |
| Mosquitto | Accepts authenticated MQTT detections over TLS on port 8883 and queues QoS 1 messages for the persistent worker session. |
| Ingestion worker | Validates each detection, stores media in MinIO, commits metadata in PostgreSQL, then sends MQTT PUBACK. |
| PostgreSQL | Stores searchable detection records and prevents duplicates by event UUID. Existing numeric IDs remain usable. |
| MinIO | Stores private JPEG snapshots and MP4 clips. A named volume is used by default. A bind mount can point to the external SSD. |
| FastAPI | Provides authenticated reads, pagination, media streaming, a small dashboard, and monitoring endpoints. |

## Start on one 64-bit Raspberry Pi or Linux host

Use the Pi 4/5 or another 64-bit Linux host for the stateful services. Run commands from this directory with Docker Engine, Compose v2, and OpenSSL installed. Use the same Compose project name as the previous deployment when upgrading on the same host, so Compose finds the existing database and object volumes. Back up both stores before upgrading. For an existing PostgreSQL volume, set the actual current database credentials. Changing the environment of the PostgreSQL container does not change an existing role's password.

1. Copy the environment template and fill in strong, distinct values.

   ```sh
   cp .env.example .env
   chmod 600 .env
   ```

2. Generate a broker certificate for the DNS name used by the sensor. Supply the LAN IP as the second argument if clients use that IP directly. Provide distinct passwords at the prompts. Put the **ingestion** password in `.env` as `MQTT_PASSWORD`. Keep the **sensor** password on the producer side.

   ```sh
   sh deploy/bootstrap-broker.sh broker.example.lan 192.168.50.10
   ```

   Set `MQTT_BIND` in `.env` to the broker's LAN address when remote devices need access. Allow port 8883 from the sensor subnet. Give producer machines only `deploy/runtime/trust/ca.crt` and their credentials. Keep the CA signing key offline after provisioning. Check certificate expiry before field tests.

3. Start the stack and follow the migration and ingestion logs.

   ```sh
   docker compose up -d --build
   docker compose ps -a
   docker compose logs migrate ingestion
   curl --fail http://localhost:8000/health/ready
   ```

   Start publishing after the ingestion client has connected at least once. Open `http://localhost:8000/` on the host for the dashboard, or `/docs` for OpenAPI. PostgreSQL and MinIO listen on the Compose network. For remote web access place an HTTPS reverse proxy in front of the API, leaving the API bound to loopback when the proxy runs on the host. Apply access restrictions and rate limits at the proxy.

The default MinIO digest pins the existing third-party multi-architecture image. Set `MINIO_IMAGE` to a team-reviewed image if required. For the isolated prototype, the services default to the Compose MinIO credentials. For a shared deployment, pre-create a private bucket and supply scoped S3 credentials with HeadBucket/ListBucket, GetObject and PutObject as appropriate. Application config and broker secrets are local and excluded from Git. Protect Docker daemon access because it can inspect container environment variables.

## External SSD

1. Mount the SSD by UUID on the storage host and configure the Docker deployment to start after that mount. For example, use `/mnt/drone-ssd` with `RequiresMountsFor=/mnt/drone-ssd` in the unit that starts Compose.
2. Use `findmnt --mountpoint /mnt/drone-ssd` to verify the mount. Create a dedicated writable directory underneath it and set `MINIO_DATA_DIR=/mnt/drone-ssd/minio` in `.env`. Give only the MinIO runtime identity access. Compose checks that the directory exists.
3. For an existing deployment, back up the MinIO data and restore it to the SSD, or migrate the objects using S3 before switching. Verify object counts and retrieve sample images from the API. Deploy with both files.

   ```sh
   docker compose -f docker-compose.yml -f compose.ssd.yml up -d --build
   ```

An SSD improves capacity and separates data from the system card. It remains a single storage device, so keep backups on another machine or storage system.

## Task 1 and Task 2 · event contract

The inspected `origin/task1-cameras` and `origin/task2-detection` branches contained no producer implementation. The contract preserves the existing Task 3 topic and base fields from its prototype publisher.

Publish UTF-8 JSON to `drone/detections` over TLS using QoS 1, with retain disabled. Process the video stream locally and send only selected events and media.

```json
{
  "event_id": "50873975-2bf5-428a-b5e9-a7004a412da3",
  "drone_id": "track-17",
  "confidence": 0.94,
  "status": "TRACKING",
  "detected_at": "2026-11-25T12:05:00Z",
  "sensor_id": "pi5-overview",
  "metadata": {"camera_id": "overview-02", "bbox_xyxy_px": [53, 80, 89, 112]}
}
```

- `drone_id` and `status` are nonempty strings up to 50 characters. `confidence` is between 0 and 1. Status remains a producer-defined label.
- Generate the UUID and capture timestamp once. Persist the event file in the sensor's local outbox and resend the same bytes after a timeout or reconnect. A naive timestamp is rejected. For older producers, omitted IDs derive from the normalized payload and identical payloads collapse. An omitted capture timestamp defaults to receipt time.
- `image_base64` accepts a JPEG up to 4 MiB. `video_base64` accepts an MP4 up to 6 MiB. Provide raw base64 without a data URL prefix. The MQTT packet limit is 16 MiB, and the decoded metadata JSON is limited to 64 KiB.
- Legacy `image_url` is stored as metadata. The API serves objects in its configured bucket and never dereferences HTTP URLs. The embedded JPEG takes precedence when both fields are supplied.
- If the same UUID is reused with different content, the worker keeps the committed record and logs a validation failure. For new events, require a producer-generated UUID.
- Broker PUBACK confirms delivery to the broker. If the producer needs to confirm database durability, retain its outbox entry until a trusted process verifies the UUID through the API. Keep API tokens away from sensors that only publish if confirmation is handled centrally.
- The broker retains a bounded offline queue per persistent session (1,000 messages or 128 MiB). A long outage can exceed that queue. A sudden broker or disk failure can also lose changes since the last persistence write. Keeping the producer outbox is required to cover these cases.

Smoke test on the sensor or workstation with Python 3.12 and the backend requirements installed. Save the JSON above as `event.json`. Set `MQTT_HOST` to the certificate name, `MQTT_CA_FILE` to the CA certificate path, `MQTT_USERNAME=sensor` and `MQTT_PASSWORD` to the sensor secret. Then run from this directory:

```sh
python -m scripts.publish_event event.json
```

The CLI sends one event file and reports a rejected or unrouted MQTT 5 publish. Retry the same file when it reports a failure. For a burst check with a real captured image use `python -m scripts.stress_test frame.jpg --count 50`. Its reported duration measures broker acknowledgements. Measure storage throughput separately by counting matching records in the API and timing the last committed record.

## REST and Task 4

| Endpoint | Result |
| --- | --- |
| `GET /api/v1/detections` | Page in descending numeric ID order. Optional `drone_id`, `sensor_id`, `since` with a timezone, `limit` from 1 to 200, and `before_id` from the prior page's `next_before_id`. |
| `GET /api/v1/detections/{id}` | Metadata for a numeric ID or event UUID. |
| `GET /api/v1/detections/{id}/image` | Streams the associated JPEG. |
| `GET /api/v1/detections/{id}/video` | Streams the associated MP4. |
| `GET /health/live` | API process responds. |
| `GET /health/ready` | Database schema and S3 bucket are reachable. |
| `GET /metrics` | Prometheus metrics including `drone_backend_ready` (1 or 0). |

Send `Authorization: Bearer <API_TOKEN>` for detections, media and metrics. The API returns 401 for bad credentials, 404 for missing events or media, 422 for invalid query parameters and 503 when a dependency request fails. For example:

```sh
curl --fail -H "Authorization: Bearer $API_TOKEN" \
  'http://localhost:8000/api/v1/detections?limit=10'
```

The Task 4 branch currently configures Raspberry Pi infrastructure metrics and does not consume backend events. Add a scrape job next to that configuration. Save the token in a Prometheus secret file readable by its process.

```yaml
- job_name: drone-backend
  scheme: https
  static_configs:
    - targets: [backend.example.lan:443]
  authorization:
    type: Bearer
    credentials_file: /run/secrets/drone-backend-api-token
```

Task 4 can alert on `up == 0` for scrape failure and `drone_backend_ready == 0` for storage dependency failure. Its detection/Telegram consumer can poll the authenticated detection feed and persist the last handled ID, fetching pages until it reaches its previous checkpoint. Node telemetry, external alert routing and bot credentials are part of Task 4.

## Cluster deployment and failure modes

For the first hardware integration, start with the single-host procedure above. The application tier can then run on the worker cluster with the [Swarm stack](deploy/swarm.yml):

1. Use two or more 64-bit Linux worker-capable nodes and a Swarm manager quorum (three managers for a one-manager failure). Label at least two eligible nodes with `docker node update --label-add drone_backend=true NODE`. [Docker Swarm manager guide](https://docs.docker.com/engine/swarm/admin_guide/)
2. Publish the application image to a team registry with `docker buildx build --platform linux/amd64,linux/arm64 -t REGISTRY/drone-backend:VERSION --push .`. Set `BACKEND_IMAGE` to that reference. Provide the PostgreSQL writer endpoint, private S3 endpoint, MQTT TLS endpoint, and the database username and S3 access-key ID to the manager environment. Create the four external Swarm secrets from locally protected files using e.g. `docker secret create drone-db-password /protected/db-password`. The other secret names are `drone-s3-secret-key`, `drone-api-token` and `drone-mqtt-password`. Use `https://` for S3. Both DB and MQTT hostnames must match their certificates. Run `python -m scripts.migrate` in the application image once with database connectivity and `DB_SSLMODE=verify-full` plus the trusted database CA path.
3. Create the Swarm config with `docker config create drone-cluster-ca /path/to/cluster-trust-bundle.crt`. Create the shared encrypted overlay with `docker network create --driver overlay --opt encrypted drone-proxy`. Attach the HTTPS ingress proxy to that overlay and point it at service `drone_api:8000`. For availability of ingress, use redundant proxy instances behind a stable entry address. Check readiness at the proxy or externally. Swarm's process health check intentionally tests liveness.
4. From a manager, run `docker stack deploy --with-registry-auth -c deploy/swarm.yml drone`. Verify `docker stack services drone`, check the TLS/API endpoints, then run the publisher smoke test. Shutdown the original Compose ingestion service before using its same persistent MQTT client ID in Swarm.
5. Drain an app node with `docker node update --availability drain NODE`. Verify the other API replica answers, publish an event while ingestion is rescheduled, and verify its UUID and media after recovery. Restore the node with `--availability active`. Repeat with a non-manager worker power interruption and record outage duration, event count and any repeated delivery.

The Swarm stack places two API replicas on separate nodes and reschedules one active ingestion worker using the same MQTT session ID. Running two workers with the same client ID makes them disconnect one another. With the provided single-host stateful services, losing their host still interrupts the entire data path. Whole-cluster HA also requires:

- **PostgreSQL:** a replicated writer with failover, fencing and a stable writer endpoint. Test promotion and decide which writes must be synchronously replicated.
- **MinIO:** a distributed installation across independent disks/nodes with quorum and a redundant endpoint. A single USB SSD cannot provide that redundancy.
- **Mosquitto:** a stable endpoint with a single fenced active broker and recoverable session storage. Mosquitto persistence is local. Independent broker replicas behind a round-robin proxy do not share sessions. Test broker restart and producer replay, and document the resulting recovery point and recovery time. [Mosquitto persistence and queue configuration](https://mosquitto.org/man/mosquitto-conf-5.html)

The worker stores media before committing its row. Stable object paths let retries reuse partially written objects. An event abandoned permanently after an object write can leave an unreferenced object. Compare private bucket inventory against referenced keys before removing any orphaned objects and keep an age buffer covering your longest replay window.

## Tests

On Windows with Docker Desktop, run the isolated integration suite from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File backend/tests/run-compose.ps1
```

This uses a unique Compose project, temporary credentials and certificates, and local ports 18000 and 18883. It removes only that project's test containers and volumes. See [test results](TASK3_PROGRESS.md) for the verified scope.
