#!/usr/bin/env python3
"""Automatic tracking: detections -> pan-tilt platform.

Stage 1: every detection of a fixed webcam is converted into pan/tilt with
angles.py, and the platform turns roughly there. The calibration from
pantilt_click.py (calibration.json) is loaded automatically.
Stage 2 (option --hq): as soon as the target is in the HQ camera image, the
platform keeps it in the centre (pantilt_hq.py). While the HQ camera sees the
target, it has priority over the webcams.

Source of the webcam detections, choose one:
  --mqtt HOST     real detections from the broker, topic sensors/+/detections
  --motion        demo without drone detection: anything that moves in the
                  webcam image is tracked (webcams as in pantilt_click.py)
  --stdin         events as JSON lines from the keyboard or a file (testing)
  --hq-only       no webcams, stage 2 only (to try out --hq)

Finding the target in the HQ image (stage 2):
  --hq sky        dark spot against a bright sky (drone outdoors)
  --hq color      coloured object, colour with --color red|yellow|green|blue (tests indoors)
  --hq mqtt       detections from Task 2 with "camera_id": "hq" (only together with --mqtt)

Event format (as in the backend, Task 3):
  {"camera_id": "cam-1", "class": "drone", "confidence": 0.87,
   "bbox": {"x": 812, "y": 240, "w": 64, "h": 40}, "track_id": 7}
  bbox in pixels of the camera, x/y = top-left corner. For the HQ camera use
  camera_id "hq" and pixels of the HQ image (1014 x 760).
  track_id is optional; if present, the platform stays with the same drone.

Examples:
  python3 pantilt_tracking.py --motion                     stage 1, demo
  python3 pantilt_tracking.py --motion --hq color          stage 1 + 2, red object
  python3 pantilt_tracking.py --hq-only --hq color         stage 2 only
  python3 pantilt_tracking.py --mqtt localhost --hq sky    real operation
Needs:   as pantilt_click.py; for --mqtt also
         Pi: sudo apt install python3-paho-mqtt   Laptop: pip install paho-mqtt
Quit:    q in an image window or Ctrl+C
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time

from pantilt_control import CAMERAS, PLATFORM, Controller, find_pico


# ---------------------------------------------------------------------------
# Logic (without hardware, so it can be tested)
# ---------------------------------------------------------------------------

class Tracker:
    """Decides which target the platform follows and when a command is sent.

    - Detections below min_confidence or with the wrong class are ignored.
    - If the tracked drone has a track_id, the platform stays with it until it
      has not been reported for switch_after_s.
    - If the HQ camera sees the target (hq_target), it has priority over the
      webcams for hq_priority_s, because it is much more precise.
    - At most one MOVE per period_s and only for changes above deadband_deg,
      so the servos do not twitch all the time.
    - Targets outside the range are approached up to the limit.
    - After home_after_s without a detection the platform returns to the home position.
    """

    def __init__(self, controller: Controller, classes=None, min_confidence=0.4, period_s=0.1,
                 deadband_deg=0.5, switch_after_s=1.0, home_after_s=10.0, home=(0.0, 30.0),
                 hq_priority_s=0.5, clock=time.monotonic):
        self.ctl = controller
        self.classes = set(classes) if classes else None
        self.min_confidence = min_confidence
        self.period_s = period_s
        self.deadband_deg = deadband_deg
        self.switch_after_s = switch_after_s
        self.home_after_s = home_after_s
        self.home = home
        self.hq_priority_s = hq_priority_s
        self.clock = clock
        self.goal = None                  # (pan, tilt) the platform should go to
        self.source = None                # "webcam" or "HQ"
        self.track = None                 # track_id of the tracked drone
        self.last_seen = None
        self.hq_last = None
        self.last_command = -1e9
        self.sent = None                  # last direction that was sent
        self.at_home = False

    def hq_leads(self) -> bool:
        return self.hq_last is not None and self.clock() - self.hq_last < self.hq_priority_s

    def event(self, e: dict) -> str | None:
        """Handle one webcam detection. Returns the reason if ignored, otherwise None."""
        try:
            cid, bbox = e["camera_id"], e["bbox"]
            confidence = float(e.get("confidence", 1.0))
        except (KeyError, TypeError, ValueError):
            return "incomplete event"
        if cid not in self.ctl.system.cameras:
            return f"unknown camera {cid}"
        if confidence < self.min_confidence:
            return "confidence too low"
        if self.classes and e.get("class") not in self.classes:
            return f"class {e.get('class')} is not tracked"
        now = self.clock()
        track = e.get("track_id")
        busy = (self.track is not None and track is not None and track != self.track
                and now - self.last_seen < self.switch_after_s)
        if busy:
            return f"following track {self.track}"
        if self.hq_leads():
            self.last_seen = now
            return "HQ camera leads"
        try:
            pan, tilt = self.ctl.system.target_from_event(e)
        except (KeyError, TypeError, ValueError):
            return "bbox not readable"
        self.goal = self.ctl.platform.clamp(pan, tilt)
        self.source = "webcam"
        self.track = track
        self.last_seen = now
        self.at_home = False
        return None

    def hq_target(self, pan: float, tilt: float):
        """Stage 2: new goal from the HQ image (see pantilt_hq.FineControl)."""
        now = self.clock()
        self.goal = self.ctl.platform.clamp(pan, tilt)
        self.source = "HQ"
        self.hq_last = now
        self.last_seen = now
        self.at_home = False

    def tick(self) -> str | None:
        """Call regularly. Sends a command if needed. Returns a message or None."""
        now = self.clock()
        if self.last_seen is not None and not self.at_home and now - self.last_seen > self.home_after_s:
            self.at_home, self.goal, self.track = True, None, None
            self.sent = self.home
            return "nothing seen any more -> home position: " + self.ctl.move(*self.home)
        if self.goal is None or now - self.last_command < self.period_s:
            return None
        if self.sent and max(abs(a - b) for a, b in zip(self.goal, self.sent)) < self.deadband_deg:
            return None
        self.last_command = now
        self.sent = self.goal
        answer = self.ctl.move(*self.goal)
        return (f"{self.source:6s} pan {self.goal[0]:+6.1f}  tilt {self.goal[1]:+6.1f}"
                f"  track {self.track}  -> {answer}")


class MotionDetector:
    """Demo detection: largest moving area in the webcam image -> event like from the drone detection."""

    def __init__(self, cid: str, camera, min_share=0.0005, max_share=0.3, warmup_frames=30):
        import cv2
        self.cv2 = cv2
        self.cid, self.camera = cid, camera
        self.background = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=40, detectShadows=False)
        self.min_share, self.max_share = min_share, max_share
        self.warmup = warmup_frames

    def image(self, img) -> dict | None:
        cv2 = self.cv2
        h, w = img.shape[:2]
        small = cv2.resize(img, (320, round(320 * h / w)))
        mask = self.background.apply(small)
        if self.warmup > 0:                       # learn the background first
            self.warmup -= 1
            return None
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        mask = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        share = cv2.contourArea(largest) / (small.shape[0] * small.shape[1])
        if not self.min_share <= share <= self.max_share:    # noise or exposure jump
            return None
        x, y, bw, bh = cv2.boundingRect(largest)
        sx, sy = self.camera.width / small.shape[1], self.camera.height / small.shape[0]
        return {"camera_id": self.cid, "class": "motion", "confidence": 1.0,
                "bbox": {"x": x * sx, "y": y * sy, "w": bw * sx, "h": bh * sy}}


def bbox_center(bbox: dict) -> tuple[float, float]:
    return bbox["x"] + bbox["w"] / 2, bbox["y"] + bbox["h"] / 2


# ---------------------------------------------------------------------------
# Sources and main loop
# ---------------------------------------------------------------------------

def start_mqtt(host: str, port: int, topic: str, target: queue.Queue):
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)     # paho-mqtt 2.x
    except AttributeError:
        client = mqtt.Client()                                      # paho-mqtt 1.x

    def connected(c, *args):
        c.subscribe(topic)
        print(f"MQTT connected to {host}:{port}, waiting for {topic}")

    def message(c, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except ValueError:
            print("no JSON on", msg.topic)
            return
        for e in data if isinstance(data, list) else [data]:
            target.put(e)

    client.on_connect, client.on_message = connected, message
    client.connect(host, port)
    client.loop_start()
    return client


def start_stdin(target: queue.Queue):
    def read():
        for line in sys.stdin:
            line = line.strip()
            if line:
                try:
                    target.put(json.loads(line))
                except ValueError:
                    print("no JSON:", line)
    threading.Thread(target=read, daemon=True).start()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Detections -> pan-tilt tracking")
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--mqtt", metavar="HOST", help="broker, e.g. localhost")
    source.add_argument("--motion", action="store_true", help="demo: track motion in the webcam image")
    source.add_argument("--stdin", action="store_true", help="events as JSON lines from standard input")
    source.add_argument("--hq-only", action="store_true", help="no webcams, stage 2 only (needs --hq)")
    ap.add_argument("--hq", choices=["off", "sky", "color", "mqtt"], default="off",
                    help="stage 2: how the target is found in the HQ image")
    ap.add_argument("--color", default="red", help="for --hq color: red, yellow, green or blue")
    ap.add_argument("--hq-gain", type=float, default=0.6,
                    help="share of the error corrected per HQ image (smaller = calmer)")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="sensors/+/detections")
    ap.add_argument("--target-class", action="append", help="track only this class, e.g. --target-class drone")
    ap.add_argument("--min-confidence", type=float, default=0.4)
    ap.add_argument("--pico", default=None, help="serial port, otherwise found automatically")
    args = ap.parse_args(argv)
    if args.hq_only and args.hq in ("off", "mqtt"):
        ap.error("--hq-only needs --hq sky or --hq color")
    if args.hq == "mqtt" and not args.mqtt:
        ap.error("--hq mqtt only works together with --mqtt")
    return args


def main():
    import serial
    args = parse_args()

    events = queue.Queue()
    webcams, detectors = {}, {}
    if args.mqtt:
        start_mqtt(args.mqtt, args.port, args.topic, events)
    elif args.stdin:
        start_stdin(events)
    elif args.motion:
        from pantilt_click import WEBCAM_DEVICES, open_webcam
        for cid, device in WEBCAM_DEVICES.items():
            webcams[cid] = open_webcam(device, CAMERAS[cid])
            detectors[cid] = MotionDetector(cid, CAMERAS[cid])
        print("Motion demo: keep still for the first seconds, then move something in front of a webcam.")

    hq = hq_detector = fine = None
    if args.hq != "off":
        import pantilt_hq
        fine = pantilt_hq.FineControl(PLATFORM, gain=args.hq_gain)
        if args.hq in ("sky", "color"):
            hq = pantilt_hq.open_hq()
            if hq is None:
                sys.exit("stage 2 needs the HQ camera")
            hq_detector = pantilt_hq.SkyDetector() if args.hq == "sky" else pantilt_hq.ColorDetector(args.color)
        print(f"Stage 2 on: the HQ camera looks for the target ({args.hq})")

    windows = bool(webcams) or hq is not None
    if windows:
        import cv2

    with serial.Serial(find_pico(args.pico), 115200, timeout=0.3) as ser:
        ctl = Controller(ser, CAMERAS, PLATFORM)
        print(ctl.message)
        tracker = Tracker(ctl, classes=args.target_class, min_confidence=args.min_confidence)
        print("Home position:", ctl.move(*tracker.home))
        try:
            while True:
                for cid, cap in webcams.items():
                    ok, img = cap.read()
                    if not ok:
                        continue
                    e = detectors[cid].image(img)
                    if e:
                        events.put(e)
                        b = e["bbox"]
                        k = CAMERAS[cid]
                        sx, sy = img.shape[1] / k.width, img.shape[0] / k.height
                        p1 = (int(b["x"] * sx), int(b["y"] * sy))
                        p2 = (int((b["x"] + b["w"]) * sx), int((b["y"] + b["h"]) * sy))
                        cv2.rectangle(img, p1, p2, (0, 255, 0), 3)
                    height = round(960 * img.shape[0] / img.shape[1])
                    cv2.imshow(cid, cv2.resize(img, (960, height)))

                if hq is not None:                              # stage 2 with our own detector
                    img = hq.capture_array()
                    hit = hq_detector.image(img)
                    if hit:
                        tracker.hq_target(*fine.target(*hit, pantilt_hq.current_position(ctl)))
                    cv2.imshow("HQ camera", pantilt_hq.hq_display(img, hit))

                while not events.empty():
                    e = events.get()
                    if e.get("camera_id") == "hq":              # stage 2 with the detection of Task 2
                        if fine and float(e.get("confidence", 1.0)) >= args.min_confidence and "bbox" in e:
                            u, v = bbox_center(e["bbox"])
                            tracker.hq_target(*fine.target(u, v, pantilt_hq.current_position(ctl)))
                        continue
                    reason = tracker.event(e)
                    if reason and not webcams and reason != "HQ camera leads":
                        print("ignored:", reason)

                message = tracker.tick()
                if message:
                    print(message)
                if windows:
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                else:
                    time.sleep(0.02)
        except KeyboardInterrupt:
            pass
        finally:
            for cap in webcams.values():
                cap.release()
            if hq is not None:
                hq.stop()
            if windows:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
