#!/usr/bin/env python3
"""Click control and calibration: show the webcam images, click into them, the platform turns there.

Every webcam gets its own window. A red circle shows where the platform points
right now (calculated with angles.py), a green cross the last click. A third
window shows the HQ camera with a crosshair.

Mouse and keys (in one of the image windows; click the title bar to select a window):
  left click    AIM mode: the platform turns to that point
                CALIBRATE mode: the click is saved as a calibration point (platform stays)
  m             switch mode: AIM <-> CALIBRATE
  w a s d       move the platform by hand (up, left, down, right)
  + / -         double / halve the step size
  h             back to 0/0
  x             delete the last calibration point (wrong click)
  c             compute and save the calibration (3+ points per webcam;
                from 6 points the edge distortion of the webcam is estimated too)
  q / Esc       quit

Calibration:
  1. Mode CALIBRATE (m).
  2. Use w a s d to move the HQ camera until a landmark sits exactly in the crosshair
     of the HQ window. Landmarks should be far away (outdoors, 20 m or more).
  3. Click the same landmark in the webcam window.
  4. Repeat for 6 landmarks per webcam, spread over the image, then press c.

Run:     python3 pantilt_click.py [--no-hq] [--pico port]
         The Pico is found automatically. On a laptop always use --no-hq,
         the HQ camera only works on the Pi.
Needs:   Pi:      sudo apt install python3-opencv python3-serial python3-numpy python3-picamera2
         Laptop:  pip install opencv-python pyserial numpy
         angles.py, pantilt_control.py and pantilt_hq.py in the same folder.
"""
import argparse
import sys

import cv2

from pantilt_control import CAMERAS, PLATFORM, Controller, find_pico
from pantilt_hq import hq_display, open_hq

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Which video device is which webcam? Names as in CAMERAS (pantilt_control.py).
#   Pi 5:    paths like "/dev/video0", find them with: v4l2-ctl --list-devices
#            (take the first /dev/videoX of each USB camera; the numbers can change after
#            a reboot, the paths under /dev/v4l/by-path/ stay fixed per USB port)
#   Laptop:  numbers. 0 is usually the built-in camera, USB webcams are 1 and 2.
#   Only one webcam connected: comment out the other line with #.
WEBCAM_DEVICES = {
    "cam-1": "/dev/video0",
    "cam-2": "/dev/video2",
}

DISPLAY_WIDTH = 960         # window width in pixels; the camera image is scaled down to it
RED, GREEN, WHITE, BLACK = (0, 0, 255), (0, 255, 0), (255, 255, 255), (0, 0, 0)


# ---------------------------------------------------------------------------
# Logic (without windows, so it can be tested)
# ---------------------------------------------------------------------------

def window_to_camera_pixel(x, y, image_size, display_size, camera):
    """Click in the (scaled) window -> pixel in the coordinates of the camera in CAMERAS.

    Also converts if the webcam delivers another resolution than set in CAMERAS.
    """
    iw, ih = image_size
    dw, dh = display_size
    u_img, v_img = x * iw / dw, y * ih / dh
    return u_img * camera.width / iw, v_img * camera.height / ih


def camera_pixel_to_window(u, v, display_size, camera):
    dw, dh = display_size
    return int(round(u * dw / camera.width)), int(round(v * dh / camera.height))


class ClickControl:
    def __init__(self, controller: Controller):
        self.ctl = controller
        self.mode = "AIM"
        self.step = 2.0
        self.last_click = {}                 # cid -> (u, v) in camera pixels
        self.last_camera = None

    def click(self, cid: str, u: float, v: float) -> str:
        self.last_click[cid] = (u, v)
        self.last_camera = cid
        text = f"{cid} {u:.1f} {v:.1f}"
        try:
            if self.mode == "AIM":
                self.ctl.message = self.ctl.target(text)
            else:
                self.ctl.message = self.ctl.add_point(text)
        except (ValueError, KeyError) as error:
            self.ctl.message = f"Error: {error}"
        return self.ctl.message

    def key(self, char: str) -> bool:
        """Handles one key. False = quit the program."""
        ctl = self.ctl
        moves = {"w": (0, 1), "s": (0, -1), "a": (-1, 0), "d": (1, 0)}
        if char in ("q", "\x1b"):
            return False
        if char in moves:
            dp, dt = moves[char]
            ctl.message = ctl.step(dp * self.step, dt * self.step)
        elif char in ("+", "="):
            self.step = min(20.0, self.step * 2)
        elif char == "-":
            self.step = max(0.25, self.step / 2)
        elif char == "h":
            ctl.message = ctl.move(0, 0)
        elif char == "m":
            self.mode = "CALIBRATE" if self.mode == "AIM" else "AIM"
            ctl.message = f"mode: {self.mode}"
        elif char == "x" and self.last_camera:
            ctl.message = ctl.delete_point(self.last_camera)
        elif char == "c":
            ctl.message = ctl.calibrate()
        return True

    def overlay(self, img, cid: str):
        """Draws platform direction, last click and status into the (scaled) image."""
        camera = self.ctl.system.cameras[cid]
        size = (img.shape[1], img.shape[0])
        aim = camera.pan_tilt_to_pixel(self.ctl.pan, self.ctl.tilt)
        if aim:
            p = camera_pixel_to_window(*aim, size, camera)
            if 0 <= p[0] < size[0] and 0 <= p[1] < size[1]:
                cv2.circle(img, p, 14, RED, 2)
                cv2.circle(img, p, 2, RED, -1)
        if cid in self.last_click:
            p = camera_pixel_to_window(*self.last_click[cid], size, camera)
            cv2.drawMarker(img, p, GREEN, cv2.MARKER_CROSS, 22, 2)
        points = len(self.ctl.points.get(cid, []))
        lines = [
            f"{cid}  mode: {self.mode}  (m switches)",
            f"platform pan {self.ctl.pan:+.1f}  tilt {self.ctl.tilt:+.1f}  step {self.step:g}  calibration points: {points}",
            self.ctl.message[:110],
            self.ctl.message[110:220],
        ]
        # dark bar behind the text so it stays readable against a bright sky
        cv2.rectangle(img, (0, 0), (img.shape[1], 8 + 22 * len(lines)), BLACK, -1)
        for i, text in enumerate(lines):
            cv2.putText(img, text, (8, 22 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1, cv2.LINE_AA)
        return img


# ---------------------------------------------------------------------------
# Cameras and windows
# ---------------------------------------------------------------------------

def open_webcam(device, camera):
    """device: number (0, 1, 2 ...) or on Linux a path like /dev/video0."""
    if sys.platform.startswith("linux"):
        cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open webcam {device}. Check WEBCAM_DEVICES (is another program using it?).")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # otherwise USB cannot do Full HD
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam {device}: delivers {w} x {h}")
    if w and h and abs(w / h - camera.width / camera.height) > 0.02:
        print(f"  WARNING: other aspect ratio than in CAMERAS ({camera.width} x {camera.height}),"
              f" enter {w} x {h} there")
    return cap


def main():
    import serial
    ap = argparse.ArgumentParser(description="Click into the webcam image -> pan-tilt turns there")
    ap.add_argument("--pico", default=None, help="serial port, otherwise found automatically")
    ap.add_argument("--no-hq", action="store_true", help="no window for the HQ camera")
    args = ap.parse_args()

    webcams = {cid: open_webcam(dev, CAMERAS[cid]) for cid, dev in WEBCAM_DEVICES.items()}
    hq = None if args.no_hq else open_hq()

    with serial.Serial(find_pico(args.pico), 115200, timeout=0.3) as ser:
        app = ClickControl(Controller(ser, CAMERAS, PLATFORM))
        app.ctl.message = app.ctl.move(0, 0) + " | " + app.ctl.message
        image_size = {}                          # cid -> (width, height) of the original image

        def mouse(event, x, y, flags, cid):
            if event == cv2.EVENT_LBUTTONDOWN and cid in image_size:
                iw, ih = image_size[cid]
                display = (DISPLAY_WIDTH, round(DISPLAY_WIDTH * ih / iw))
                app.click(cid, *window_to_camera_pixel(x, y, (iw, ih), display, CAMERAS[cid]))

        for cid in webcams:
            cv2.namedWindow(cid, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(cid, mouse, cid)

        try:
            while True:
                for cid, cap in webcams.items():
                    ok, img = cap.read()
                    if not ok:
                        continue
                    image_size[cid] = (img.shape[1], img.shape[0])
                    height = round(DISPLAY_WIDTH * img.shape[0] / img.shape[1])
                    small = cv2.resize(img, (DISPLAY_WIDTH, height))
                    cv2.imshow(cid, app.overlay(small, cid))
                if hq is not None:
                    cv2.imshow("HQ camera", hq_display(hq.capture_array()))
                key = cv2.waitKey(1) & 0xFF
                if key != 255 and not app.key(chr(key)):
                    break
        finally:
            for cap in webcams.values():
                cap.release()
            if hq is not None:
                hq.stop()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
