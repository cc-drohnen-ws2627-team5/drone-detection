"""
Task 4 - Telegram Drone Detection Notification

Polls the Task 3 backend API for new detection events
and sends notifications through the Telegram Bot API.

Status: Prepared for integration testing.
"""

import json
import os
import time

from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = os.environ["BACKEND_API_URL"].rstrip("/")
API_TOKEN = os.environ["API_TOKEN"]

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

POLL_INTERVAL = 5

STATE_FILE = Path(
    os.getenv("NOTIFIER_STATE_FILE", "notifier_state.json")
)


def load_state():
    if STATE_FILE.exists():
        with STATE_FILE.open() as file:
            return int(json.load(file)["last_id"])

    return None


def save_state(last_id):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    temporary = STATE_FILE.with_suffix(".tmp")

    with temporary.open("w") as file:
        json.dump({"last_id": last_id}, file)

    temporary.replace(STATE_FILE)


def fetch_detections(before_id=None, limit=200):
    params = {"limit": limit}

    if before_id is not None:
        params["before_id"] = before_id

    url = (
        API_URL
        + "/api/v1/detections?"
        + urlencode(params)
    )

    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {API_TOKEN}"
        }
    )

    with urlopen(request, timeout=15) as response:
        return json.load(response)


def fetch_new_events(last_id):
    events = []
    before_id = None

    while True:
        data = fetch_detections(before_id)

        for event in data["items"]:
            if int(event["id"]) <= last_id:
                return sorted(
                    events,
                    key=lambda item: int(item["id"])
                )

            events.append(event)

        before_id = data.get("next_before_id")

        if before_id is None:
            break

    return sorted(
        events,
        key=lambda item: int(item["id"])
    )


def is_test_event(event):
    drone_id = str(event.get("drone_id", ""))
    sensor_id = str(event.get("sensor_id", ""))

    return (
        drone_id.startswith(("load-", "latency-"))
        or drone_id == "drone-load-test"
        or sensor_id in (
            "performance-test",
            "latency-test"
        )
    )


def format_message(event):
    confidence = float(event["confidence"]) * 100

    return (
        "🚨 DRONE DETECTED\n\n"
        f"Drone ID: {event.get('drone_id', 'Unknown')}\n"
        f"Confidence: {confidence:.1f}%\n"
        f"Status: {event.get('status', 'Unknown')}\n"
        f"Sensor: {event.get('sensor_id') or 'Unknown'}\n"
        f"Detection Time: {event.get('detected_at')}\n"
        f"Event ID: {event.get('event_id')}"
    )


def send_telegram(message):
    url = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
        + "/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urlopen(request, timeout=15) as response:
        result = json.load(response)

    if not result.get("ok"):
        raise RuntimeError("Telegram delivery failed")


def main():
    print("Telegram detection notifier started")

    last_id = load_state()

    while True:
        try:
            # First startup: skip historical detections.
            if last_id is None:
                data = fetch_detections(limit=1)

                last_id = (
                    int(data["items"][0]["id"])
                    if data["items"] else 0
                )

                save_state(last_id)

                print("Initial checkpoint:", last_id)

            events = fetch_new_events(last_id)

            for event in events:

                event_id = int(event["id"])

                if not is_test_event(event):
                    send_telegram(
                        format_message(event)
                    )

                    print(
                        "Notification sent:",
                        event["event_id"]
                    )

                    # Reduce Telegram request bursts.
                    time.sleep(1)

                save_state(event_id)
                last_id = event_id

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("Notifier stopped")
            break

        except Exception as error:
            # Do not print URLs or credentials.
            print(
                "Notifier error:",
                type(error).__name__
            )

            time.sleep(30)


if __name__ == "__main__":
    main()
