#!/usr/bin/env python3
"""Pan-tilt control on the Pi 5: connection to the Pico, settings and keyboard control.

Keys:
  arrow keys   move the platform (degrees, 0/0 = straight ahead and level)
  + / -        double / halve the step size
  h            back to 0/0
  t            go to a target: enter camera and pixel, e.g. "cam-2 1500 300"
  p            add a calibration point: the HQ camera points at a landmark right now,
               enter the camera and the pixel of that landmark in the webcam image
  c            compute the calibration (3+ points per webcam) and save it
  q            quit

Run:     python3 pantilt_control.py [port]
         The Pico is found automatically. Only if that fails, give the port:
         /dev/ttyACM0 (Pi), /dev/cu.usbmodem... (Mac), COM3 (Windows).
Needs:   Pi:      sudo apt install python3-serial python3-numpy
         Laptop:  pip install pyserial numpy   (Windows also: windows-curses)
         angles.py in the same folder, Thonny closed.
"""
import json
import sys
from pathlib import Path

try:
    import curses
except ImportError:          # Windows without windows-curses: the click program still works
    curses = None

import numpy as np

from angles import Axis, Camera, CameraSystem, Platform, calibrate_camera

# ---------------------------------------------------------------------------
# Settings: enter your values here
# ---------------------------------------------------------------------------

# Fixed webcams: resolution, horizontal field of view and rough orientation (pan, tilt)
# as seen from the platform. The calibration replaces the orientation and also
# estimates the real field of view and the edge distortion.
# Our webcams: LL1 USB webcam, 100 degrees according to the maker. That is probably the
# diagonal, which is about 92 degrees horizontally at 16:9.
CAMERAS = {
    "cam-1": Camera.from_fov(1920, 1080, hfov_deg=92, orientation=(-30, 25)),
    "cam-2": Camera.from_fov(1920, 1080, hfov_deg=92, orientation=(30, 25)),
}

# Servo angle at 0/0 and direction, measured on our platform (15 Nov 2026):
#   pan:  servo 90 = straight ahead, larger = turns left       -> direction -1
#   tilt: servo 180 = level to the front, 90 = straight up     -> center 180, direction -1
#         (servo 0-90 tilts over the top to the back; not used yet)
PLATFORM = Platform(
    pan=Axis(center=90, direction=-1, minimum=0, maximum=180),
    tilt=Axis(center=180, direction=-1, minimum=90, maximum=180),
)

CALIBRATION_FILE = Path(__file__).with_name("calibration.json")
OLD_CALIBRATION_FILE_NAME = "kalibrierung.json"      # written by the earlier German version

PICO_USB_ID = 0x2E8A        # USB vendor ID of Raspberry Pi (Pico)


# ---------------------------------------------------------------------------
# Logic (without screen, so it can be tested)
# ---------------------------------------------------------------------------

class Controller:
    def __init__(self, ser, cameras=CAMERAS, platform=PLATFORM, calibration_file=CALIBRATION_FILE):
        self.ser = ser
        self.system = CameraSystem(cameras)
        self.platform = platform
        self.file = Path(calibration_file)
        self.pan = 0.0
        self.tilt = 0.0
        self.points = {cid: [] for cid in cameras}       # calibration points per webcam: (u, v, pan, tilt)
        self.message = self.load()

    def send(self, command: str) -> str:
        self.ser.reset_input_buffer()
        self.ser.write((command + "\n").encode())
        return self.ser.readline().decode(errors="replace").strip() or "(no answer)"

    def move(self, pan: float, tilt: float) -> str:
        if not self.platform.reachable(pan, tilt):
            return f"out of range: pan {pan:+.1f}, tilt {tilt:+.1f} (beyond the servo limits)"
        self.pan, self.tilt = pan, tilt
        return self.send(self.platform.move_command(pan, tilt))

    def step(self, d_pan: float, d_tilt: float) -> str:
        return self.move(self.pan + d_pan, self.tilt + d_tilt)

    def target(self, text: str) -> str:
        cid, u, v = self._camera_pixel(text)
        pan, tilt = self.system.pan_tilt(cid, u, v)
        answer = self.move(pan, tilt)
        return f"{cid} ({u:.0f}, {v:.0f}) -> pan {pan:+.2f}, tilt {tilt:+.2f}: {answer}"

    def add_point(self, text: str) -> str:
        cid, u, v = self._camera_pixel(text)
        self.points[cid].append((u, v, self.pan, self.tilt))
        return f"point {len(self.points[cid])} for {cid} saved (pan {self.pan:+.1f}, tilt {self.tilt:+.1f})"

    def delete_point(self, cid: str) -> str:
        if not self.points.get(cid):
            return f"{cid}: no points to delete"
        self.points[cid].pop()
        return f"last point of {cid} deleted, {len(self.points[cid])} left"

    def calibrate(self) -> str:
        """From 3 points the orientation, from 4 also the field of view, from 6 also the edge distortion."""
        results, data = [], self._read_file()
        for cid, measurements in self.points.items():
            n = len(measurements)
            if n < 3:
                results.append(f"{cid}: {n}/3 points")
                continue
            k = self.system.cameras[cid]
            res = calibrate_camera(k, measurements, fov=n >= 4, distortion=n >= 6)
            k.rotation, k.fx, k.fy, k.division = res["rotation"], res["fx"], res["fy"], res["division"]
            data[cid] = {"rotation": res["rotation"].tolist(), "fx": res["fx"], "fy": res["fy"],
                         "division": res["division"], "points": [list(m) for m in measurements]}
            per_point = res["errors_per_point"]
            worst = int(np.argmax(per_point))
            results.append(
                f"{cid}: error {res['error']:.2f} deg with {n} points"
                f" (field of view {res['hfov_deg']:.0f} deg, orientation only would be {res['error_rotation_only']:.1f};"
                f" worst point {worst + 1}: {per_point[worst]:.1f} deg)")
        self.file.write_text(json.dumps(data, indent=2))
        return " | ".join(results) + f"  -> saved to {self.file.name}"

    def load(self) -> str:
        data = self._read_file()
        loaded = [cid for cid in data if cid in self.system.cameras]
        for cid in loaded:
            k, d = self.system.cameras[cid], data[cid]
            if isinstance(d, list):                       # oldest format: rotation only
                k.rotation = np.array(d, dtype=float)
            else:
                k.rotation = np.array(d["rotation"], dtype=float)
                k.fx, k.fy = d["fx"], d["fy"]
                k.division = d.get("division", d.get("rand", 0.0))   # "rand" = German version
        return f"calibration loaded: {', '.join(loaded)}" if loaded else "no calibration yet"

    def _read_file(self) -> dict:
        for path in (self.file, self.file.with_name(OLD_CALIBRATION_FILE_NAME)):
            try:
                return json.loads(path.read_text())
            except (OSError, ValueError):
                continue
        return {}

    def _camera_pixel(self, text: str):
        parts = text.split()
        if len(parts) != 3:
            raise ValueError('format: "<camera> <u> <v>", e.g. "cam-1 960 540"')
        if parts[0] not in self.system.cameras:
            raise ValueError(f"unknown camera {parts[0]}, known: {', '.join(self.system.cameras)}")
        return parts[0], float(parts[1]), float(parts[2])


def find_pico(wish=None, ports=None) -> str:
    """Finds the serial port of the Pico, on the Pi, a Mac or Windows."""
    if wish:
        return wish
    if ports is None:
        from serial.tools import list_ports
        ports = list(list_ports.comports())
    picos = sorted(p.device for p in ports if p.vid == PICO_USB_ID)
    if not picos:
        raise RuntimeError("No Pico found. Check the USB cable (must be a data cable) and close Thonny.")
    # on a Mac every port shows up twice (tty. and cu.); cu. is the right one
    return next((p for p in picos if "/cu." in p), picos[0])


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

def line(scr, y: int, text: str):
    """Print text, cut to the window width (narrow terminals)."""
    height, width = scr.getmaxyx()
    if y < height:
        try:
            scr.addstr(y, 0, text[:width - 1])
        except curses.error:
            pass


def read_input(scr, row: int, question: str) -> str:
    curses.echo()
    curses.curs_set(1)
    scr.timeout(-1)
    scr.move(row, 0)
    scr.clrtoeol()
    line(scr, row, question)
    text = scr.getstr(row, min(len(question), scr.getmaxyx()[1] - 2), 40).decode(errors="replace")
    curses.noecho()
    curses.curs_set(0)
    scr.timeout(200)
    return text


def screen(scr, ctl: Controller):
    curses.curs_set(0)
    scr.timeout(200)
    step = 2.0
    ctl.message = ctl.move(0, 0) + " | " + ctl.message
    while True:
        scr.erase()
        line(scr, 0, "Pan-tilt control")
        line(scr, 1, "arrows: move  +/-: step  h: centre  q: quit")
        line(scr, 2, "t: go to target  p: calibration point  c: calibrate")
        line(scr, 4, f"Platform: pan {ctl.pan:+6.1f}  tilt {ctl.tilt:+6.1f}  deg   step {step:.1f}")
        sp, st = ctl.platform.servo_angles(ctl.pan, ctl.tilt)
        line(scr, 5, f"Servos:   {sp:6.1f}  {st:6.1f}   Pico: {ctl.send('POS?')}")
        points = "  ".join(f"{cid}: {len(p)}" for cid, p in ctl.points.items())
        line(scr, 6, f"Calibration points: {points}")
        line(scr, 8, ctl.message)
        scr.refresh()

        key = scr.getch()
        try:
            if key in (ord("q"), ord("Q")):
                break
            elif key == curses.KEY_LEFT:
                ctl.message = ctl.step(-step, 0)
            elif key == curses.KEY_RIGHT:
                ctl.message = ctl.step(step, 0)
            elif key == curses.KEY_UP:
                ctl.message = ctl.step(0, step)
            elif key == curses.KEY_DOWN:
                ctl.message = ctl.step(0, -step)
            elif key in (ord("+"), ord("=")):
                step = min(20.0, step * 2)
            elif key == ord("-"):
                step = max(0.25, step / 2)
            elif key == ord("h"):
                ctl.message = ctl.move(0, 0)
            elif key == ord("t"):
                ctl.message = ctl.target(read_input(scr, 10, "Target (camera u v): "))
            elif key == ord("p"):
                ctl.message = ctl.add_point(read_input(scr, 10, "Point in the webcam image (camera u v): "))
            elif key == ord("c"):
                ctl.message = ctl.calibrate()
        except (ValueError, KeyError) as error:
            ctl.message = f"Error: {error}"


def main():
    import serial
    if curses is None:
        sys.exit("On Windows first run: pip install windows-curses")
    port = find_pico(sys.argv[1] if len(sys.argv) > 1 else None)
    with serial.Serial(port, 115200, timeout=0.3) as ser:
        curses.wrapper(screen, Controller(ser))


if __name__ == "__main__":
    main()
