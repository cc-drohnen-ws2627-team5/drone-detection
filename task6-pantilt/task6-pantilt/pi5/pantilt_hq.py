#!/usr/bin/env python3
"""Stage 2 of Task 6: the HQ camera keeps the target in the centre of its image.

Stage 1 turns the platform roughly towards the target using the webcams. From
then on this module looks into the HQ camera image, finds the target and
corrects: if it is left of the centre, the platform turns a bit to the left
until it is centred. Calibration errors, the distance between webcams and
platform, and sagging servos are compensated automatically.

How the target is found in the HQ image (detectors):
  sky      dark spot against a bright sky (drone outdoors)
  color    coloured object, e.g. a red ball (tests indoors)
  mqtt     detections from Task 2 with camera_id "hq" (their model on the HQ image)

Used by pantilt_tracking.py (option --hq). Needs angles.py in the same folder.
"""
from __future__ import annotations

import math

from angles import Camera

HQ_ID = "hq"                      # camera_id of the HQ camera in MQTT events
HQ_SIZE = (1014, 760)             # image size the HQ camera is read with
HQ_FOV = (22.2, 16.7)             # 16 mm lens on the HQ camera, degrees (datasheet)
HQ_ROTATE = True                  # camera is mounted upside down -> rotate image by 180 degrees

RED, GREEN = (0, 0, 255), (0, 255, 0)


# ---------------------------------------------------------------------------
# Maths: where does the platform have to go to bring the target to the centre?
# ---------------------------------------------------------------------------

def pan_tilt_in_hq_image(u, v, current_pan, current_tilt, size=HQ_SIZE, fov=HQ_FOV):
    """Pixel (u, v) in the HQ image -> direction (pan, tilt) of that point.

    current_pan, current_tilt: where the platform pointed when the image was taken.
    """
    hq = Camera.from_fov(size[0], size[1], fov[0], fov[1], orientation=(current_pan, current_tilt))
    return hq.pixel_to_pan_tilt(u, v)


class FineControl:
    """Computes the next platform target from the position of the target in the HQ image.

    gain < 1: correct only part of the error per image. The image is already a
    little old when it arrives; a full correction would overshoot and oscillate.
    max_step_deg: upper limit per correction, in case the detector is wrong once.
    """

    def __init__(self, platform, gain=0.6, max_step_deg=8.0, size=HQ_SIZE, fov=HQ_FOV):
        self.platform = platform
        self.gain = gain
        self.max_step = max_step_deg
        self.size, self.fov = size, fov

    def error_deg(self, u, v, current) -> tuple[float, float]:
        """How far is the target from the image centre? (d_pan, d_tilt) in degrees."""
        pan, tilt = pan_tilt_in_hq_image(u, v, current[0], current[1], self.size, self.fov)
        d_pan = (pan - current[0] + 180) % 360 - 180
        return d_pan, tilt - current[1]

    def target(self, u, v, current) -> tuple[float, float]:
        d_pan, d_tilt = self.error_deg(u, v, current)
        limit = lambda d: max(-self.max_step, min(self.max_step, d))
        return (current[0] + self.gain * limit(d_pan),
                current[1] + self.gain * limit(d_tilt))


def current_position(controller) -> tuple[float, float]:
    """Where is the platform right now? Asks the Pico (POS?), otherwise the last command."""
    answer = controller.send("POS?").split()
    if len(answer) == 3 and answer[0] == "POS":
        try:
            servo_pan, servo_tilt = float(answer[1]), float(answer[2])
        except ValueError:
            pass
        else:
            p = controller.platform
            return p.pan.from_servo(servo_pan), p.tilt.from_servo(servo_tilt)
    return controller.pan, controller.tilt


# ---------------------------------------------------------------------------
# Detectors: where is the target in the HQ image?
# ---------------------------------------------------------------------------

class SkyDetector:
    """Dark spot against a bright sky, e.g. a drone.

    Every pixel is compared with its bright surroundings. Anything clearly darker
    than its surroundings and small enough is a candidate. With several candidates
    the one closest to the last hit wins, otherwise the one with the most contrast.
    """

    def __init__(self, threshold=35, min_area=4, max_share=0.05, min_brightness=90):
        import cv2
        self.cv2 = cv2
        self.threshold = threshold
        self.min_area = min_area
        self.max_share = max_share
        self.min_brightness = min_brightness
        self.last = None

    def image(self, img):
        cv2 = self.cv2
        h, w = img.shape[:2]
        gray = cv2.cvtColor(cv2.resize(img, (w // 2, h // 2)), cv2.COLOR_BGR2GRAY)
        surroundings = cv2.blur(gray, (41, 41))
        darker = cv2.subtract(surroundings, gray)
        _, mask = cv2.threshold(darker, self.threshold, 255, cv2.THRESH_BINARY)
        mask[surroundings < self.min_brightness] = 0          # only against a bright background
        mask = cv2.dilate(mask, None, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in contours:
            area = cv2.contourArea(c) + 1
            if not self.min_area <= area <= self.max_share * gray.size:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            contrast = float(darker[y:y + bh, x:x + bw].max())
            candidates.append(((x + bw / 2) * 2, (y + bh / 2) * 2, contrast))
        if not candidates:
            self.last = None
            return None
        if self.last:
            lu, lv = self.last
            best = min(candidates, key=lambda k: math.hypot(k[0] - lu, k[1] - lv))
        else:
            best = max(candidates, key=lambda k: k[2])
        self.last = best[:2]
        return self.last


COLORS = {                         # HSV ranges in OpenCV (H 0-179)
    "red": [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (179, 255, 255))],
    "yellow": [((20, 120, 100), (35, 255, 255))],
    "green": [((40, 80, 60), (85, 255, 255))],
    "blue": [((100, 120, 60), (130, 255, 255))],
}


class ColorDetector:
    """Largest spot of one colour, e.g. a red ball. For tests indoors."""

    def __init__(self, color="red", min_share=0.0005):
        import cv2
        import numpy as np
        if color not in COLORS:
            raise ValueError(f"unknown colour {color}, possible: {', '.join(COLORS)}")
        self.cv2, self.np = cv2, np
        self.ranges = COLORS[color]
        self.min_share = min_share

    def image(self, img):
        cv2, np = self.cv2, self.np
        h, w = img.shape[:2]
        hsv = cv2.cvtColor(cv2.resize(img, (w // 2, h // 2)), cv2.COLOR_BGR2HSV)
        mask = None
        for low, high in self.ranges:
            m = cv2.inRange(hsv, np.array(low), np.array(high))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < self.min_share * hsv.shape[0] * hsv.shape[1]:
            return None
        m = cv2.moments(largest)
        return m["m10"] / m["m00"] * 2, m["m01"] / m["m00"] * 2


# ---------------------------------------------------------------------------
# Camera and display
# ---------------------------------------------------------------------------

def open_hq(size=HQ_SIZE, rotate=HQ_ROTATE):
    try:
        from picamera2 import Picamera2
        from libcamera import Transform
    except ImportError:
        print("picamera2 not installed, no HQ camera (sudo apt install python3-picamera2)")
        return None
    hq = Picamera2()
    hq.configure(hq.create_preview_configuration(
        main={"size": size, "format": "RGB888"},
        transform=Transform(hflip=int(rotate), vflip=int(rotate))))
    hq.start()
    return hq


def hq_display(img, hit=None):
    """Crosshair in the centre, circle around the target that was found."""
    import cv2
    h, w = img.shape[:2]
    cv2.line(img, (w // 2 - 30, h // 2), (w // 2 + 30, h // 2), RED, 1)
    cv2.line(img, (w // 2, h // 2 - 30), (w // 2, h // 2 + 30), RED, 1)
    cv2.circle(img, (w // 2, h // 2), 12, RED, 1)
    if hit:
        cv2.circle(img, (int(hit[0]), int(hit[1])), 18, GREEN, 2)
    return img
