"""
Task 4 - Backend Performance Evaluation
Measures MQTT publishing and backend storage throughput.

Status: Prepared for integration testing.
"""

import argparse
import base64
import csv
import json
import os
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from .publish_event import publisher


def fetch_stored_events(api_url, token, run_id):
    stored = set()
    before_id = None

    while True:
        params = {"drone_id": run_id, "limit": 200}

        if before_id is not None:
            params["before_id"] = before_id

        url = (
            api_url.rstrip("/")
            + "/api/v1/detections?"
            + urlencode(params)
        )

        request = Request(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )

        with urlopen(request, timeout=15) as response:
            data = json.load(response)

        for item in data["items"]:
            stored.add(str(item["event_id"]))

        before_id = data.get("next_before_id")

        if before_id is None:
            return stored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--rate", type=int, default=5)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--wait", type=int, default=60)
    parser.add_argument("--output", default="performance_results.csv")
    args = parser.parse_args()

    if min(args.rate, args.duration, args.workers, args.wait) <= 0:
        parser.error("Rate, duration, workers and wait must be positive")

    api_url = os.environ["BACKEND_API_URL"]
    token = os.environ["API_TOKEN"]

    image = base64.b64encode(
        args.image.read_bytes()
    ).decode()

    run_id = "load-" + uuid4().hex
    target_events = args.rate * args.duration

    # Each worker uses its own MQTT connection.
    # Do not share the Task 3 publisher between threads.

    def worker(index):
        acknowledged = set()
        attempted = set()
        errors = 0

        with publisher() as send:
            for i in range(index, target_events, args.workers):
                scheduled = start + i / args.rate
                time.sleep(max(0, scheduled - time.monotonic()))

                if time.monotonic() >= start + args.duration:
                    break

                event_id = str(uuid4())

                payload = {
                    "event_id": event_id,
                    "drone_id": run_id,
                    "confidence": 0.9,
                    "status": "TRACKING",
                    "detected_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "sensor_id": "performance-test",
                    "image_base64": image
                }

                attempted.add(event_id)

                try:
                    send(json.dumps(payload).encode())
                    acknowledged.add(event_id)
                except Exception as error:
                    errors += 1
                    print("Publishing error:", type(error).__name__)
                    break

        return attempted, acknowledged, errors

    print("Starting backend performance test")
    print("Run ID:", run_id)
    print("Target rate:", args.rate, "events/s")
    print("Target events:", target_events)

    start = time.monotonic()

    attempted = set()
    acknowledged = set()
    errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for sent, confirmed, failed in executor.map(
            worker, range(args.workers)
        ):
            attempted.update(sent)
            acknowledged.update(confirmed)
            errors += failed

    publishing_duration = time.monotonic() - start

    # Verify unique stored events through the backend API.

    deadline = time.monotonic() + args.wait

    while True:
        stored = fetch_stored_events(api_url, token, run_id)
        verified = stored.intersection(attempted)

        if attempted.issubset(stored):
            break

        if time.monotonic() >= deadline:
            break

        time.sleep(1)

    total_duration = time.monotonic() - start

    result = {
        "run_id": run_id,
        "target_rate": args.rate,
        "target_events": target_events,
        "attempted_events": len(attempted),
        "broker_acknowledged": len(acknowledged),
        "stored_events": len(verified),
        "publishing_errors": errors,
        "not_verified": len(attempted - verified),
        "publishing_duration_s": round(publishing_duration, 3),
        "total_duration_s": round(total_duration, 3),
        "broker_throughput": round(
            len(acknowledged) / publishing_duration, 3
        ),
        "verified_throughput": round(
            len(verified) / total_duration, 3
        ),
        "success_rate_percent": round(
            100 * len(verified) / max(len(attempted), 1), 2
        )
    }

    output = Path(args.output)
    write_header = not output.exists() or output.stat().st_size == 0

    with output.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=result.keys())

        if write_header:
            writer.writeheader()

        writer.writerow(result)

    print(json.dumps(result, indent=2))
    print("Results saved to:", output)


if __name__ == "__main__":
    main()
