"""
Task 4 - Backend Latency Evaluation

Measures the observed latency from simulated detection
to successful retrieval through the backend REST API.

Status: Prepared for integration testing.
"""

import argparse
import base64
import csv
import json
import math
import os
import statistics
import time

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4

from .publish_event import publisher


def wait_for_event(api_url, token, event_id, timeout, interval):
    deadline = time.monotonic() + timeout

    url = (
        api_url.rstrip("/")
        + "/api/v1/detections/"
        + event_id
    )

    while time.monotonic() < deadline:
        request = Request(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )

        try:
            with urlopen(request, timeout=5) as response:
                data = json.load(response)

                if str(data["event_id"]) == event_id:
                    return time.monotonic()

        except HTTPError as error:
            if error.code not in (404, 503):
                raise

        except (URLError, TimeoutError):
            pass

        time.sleep(interval)

    return None


def percentile_95(values):
    ordered = sorted(values)
    index = math.ceil(0.95 * len(ordered)) - 1
    return ordered[index]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("image", type=Path)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--poll", type=float, default=0.1)
    parser.add_argument("--load-condition", default="Idle")
    parser.add_argument("--output", default="latency_results.csv")

    args = parser.parse_args()

    if min(
        args.samples,
        args.timeout,
        args.poll
    ) <= 0 or args.interval < 0:
        parser.error("Invalid test parameters")

    api_url = os.environ["BACKEND_API_URL"]
    token = os.environ["API_TOKEN"]

    image = base64.b64encode(
        args.image.read_bytes()
    ).decode()

    run_id = "latency-" + uuid4().hex

    latencies = []
    failed = 0
    samples = []

    print("Starting latency evaluation")
    print("Run ID:", run_id)
    print("Load condition:", args.load_condition)

    with publisher() as send:

        for i in range(args.samples):

            event_id = str(uuid4())

            detected_at = datetime.now(
                timezone.utc
            ).isoformat()

            start = time.monotonic()

            payload = {
                "event_id": event_id,
                "drone_id": run_id,
                "confidence": 0.9,
                "status": "TRACKING",
                "sensor_id": "latency-test",
                "detected_at": detected_at,
                "image_base64": image
            }

            latency_ms = None
            status = "Failed"

            try:
                send(json.dumps(payload).encode())

                end = wait_for_event(
                    api_url,
                    token,
                    event_id,
                    args.timeout,
                    args.poll
                )

                if end is not None:
                    latency_ms = (end - start) * 1000
                    latencies.append(latency_ms)
                    status = "Success"

                    print(
                        f"Sample {i + 1}: "
                        f"{latency_ms:.2f} ms"
                    )

                else:
                    failed += 1
                    status = "Timeout"
                    print(f"Sample {i + 1}: Timeout")

            except Exception as error:
                failed += 1
                print(
                    f"Sample {i + 1}: "
                    f"{type(error).__name__}"
                )

            samples.append({
                "run_id": run_id,
                "sample": i + 1,
                "event_id": event_id,
                "detected_at": detected_at,
                "load_condition": args.load_condition,
                "latency_ms": (
                    round(latency_ms, 2)
                    if latency_ms is not None else ""
                ),
                "status": status
            })

            time.sleep(args.interval)

    result = {
        "run_id": run_id,
        "load_condition": args.load_condition,
        "total_samples": args.samples,
        "successful_samples": len(latencies),
        "failed_samples": failed,
        "min_latency_ms": "",
        "avg_latency_ms": "",
        "median_latency_ms": "",
        "p95_latency_ms": "",
        "max_latency_ms": ""
    }

    if latencies:
        result.update({
            "min_latency_ms": round(min(latencies), 2),
            "avg_latency_ms": round(
                statistics.mean(latencies), 2
            ),
            "median_latency_ms": round(
                statistics.median(latencies), 2
            ),
            "p95_latency_ms": round(
                percentile_95(latencies), 2
            ),
            "max_latency_ms": round(max(latencies), 2)
        })

    output = Path(args.output)

    write_header = (
        not output.exists()
        or output.stat().st_size == 0
    )

    with output.open("a", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=result.keys()
        )

        if write_header:
            writer.writeheader()

        writer.writerow(result)

    sample_output = output.with_name(
        output.stem + "_samples.csv"
    )

    write_header = (
        not sample_output.exists()
        or sample_output.stat().st_size == 0
    )

    with sample_output.open("a", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=samples[0].keys()
        )

        if write_header:
            writer.writeheader()

        writer.writerows(samples)

    print(json.dumps(result, indent=2))
    print("Summary saved to:", output)
    print("Raw samples saved to:", sample_output)


if __name__ == "__main__":
    main()
