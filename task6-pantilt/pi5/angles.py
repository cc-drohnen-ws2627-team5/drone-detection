"""Angle calculation for the pan-tilt tracking (Task 6).

Converts a detection in a fixed camera (pixel u, v) into pan and tilt angles of
the platform, and those into servo angles for the Pico.

Coordinate systems (as in OpenCV):
  camera:  x to the right, y down, z along the viewing direction
  base:    the pan-tilt platform at pan = 0, tilt = 0,
           also x to the right, y down, z forward
  pan > 0: turn right,  tilt > 0: tilt up

Example:
  cam = Camera.from_fov(1920, 1080, hfov_deg=92, orientation=(30, 10))
  pan, tilt = cam.pixel_to_pan_tilt(1500, 400)
  command = platform.move_command(pan, tilt)        # e.g. "MOVE 117.3 98.1"

Only numpy is needed, no OpenCV.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def direction(pan_deg: float, tilt_deg: float) -> np.ndarray:
    """Unit vector in the base frame that points to (pan, tilt)."""
    p, t = math.radians(pan_deg), math.radians(tilt_deg)
    return np.array([math.cos(t) * math.sin(p), -math.sin(t), math.cos(t) * math.cos(p)])


def ray_to_pan_tilt(ray) -> tuple[float, float]:
    """Direction vector in the base frame -> (pan, tilt) in degrees."""
    x, y, z = np.asarray(ray, float)
    return math.degrees(math.atan2(x, z)), math.degrees(math.atan2(-y, math.hypot(x, z)))


def rotation_from_orientation(pan_deg: float, tilt_deg: float, roll_deg: float = 0.0) -> np.ndarray:
    """Rotation camera -> base for a camera whose image centre points to (pan, tilt).

    roll_deg turns the image around the viewing direction (camera mounted slightly crooked).
    """
    p, t, r = map(math.radians, (pan_deg, tilt_deg, roll_deg))
    turn_pan = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    turn_tilt = np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    turn_roll = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return turn_pan @ turn_tilt @ turn_roll


def bbox_center(bbox: dict) -> tuple[float, float]:
    """Centre of a bounding box in the event format {"x", "y", "w", "h"} (pixels, x/y = top left)."""
    return bbox["x"] + bbox["w"] / 2, bbox["y"] + bbox["h"] / 2


def calibrate_rotation(pairs) -> np.ndarray:
    """Estimates the rotation camera -> base from measurement pairs (Kabsch algorithm).

    pairs: list of (camera_ray, (pan, tilt)), with camera_ray from Camera.camera_ray(u, v)
    for a landmark and the pan/tilt angles at which the HQ camera points exactly at it.
    At least 3 pairs, better 6, spread over the image.
    """
    if len(pairs) < 3:
        raise ValueError("at least 3 pairs needed")
    a = np.array([np.asarray(s, float) / np.linalg.norm(s) for s, _ in pairs])
    b = np.array([direction(p, t) for _, (p, t) in pairs])
    u, _, vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    return vt.T @ np.diag([1.0, 1.0, d]) @ u.T


def angle_errors_deg(rotation: np.ndarray, pairs) -> list[float]:
    """Angle error (degrees) of every pair: how far off is the calculated direction?"""
    errors = []
    for s, (p, t) in pairs:
        v = rotation @ (np.asarray(s, float) / np.linalg.norm(s))
        cos = float(np.clip(v @ direction(p, t), -1.0, 1.0))
        errors.append(math.degrees(math.acos(cos)))
    return errors


def mean_angle_error_deg(rotation: np.ndarray, pairs) -> float:
    return float(np.mean(angle_errors_deg(rotation, pairs)))


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

@dataclass
class Camera:
    """A fixed camera with its intrinsics and its orientation relative to the platform."""
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    distortion: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)   # OpenCV order k1, k2, p1, p2, k3
    rotation: np.ndarray = field(default_factory=lambda: np.eye(3))
    # Edge distortion of wide-angle webcams as a single value (division model, Fitzgibbon):
    # undistorted = distorted / (1 + division * r^2). Negative = barrel (typical for wide angle).
    # Estimated by calibrate_camera; 0 = no distortion.
    division: float = 0.0

    @classmethod
    def from_fov(cls, width: int, height: int, hfov_deg: float,
                 vfov_deg: float | None = None, orientation=(0.0, 0.0, 0.0)) -> "Camera":
        """Without calibration: focal length from the horizontal field of view (datasheet).

        orientation = (pan, tilt[, roll]) in degrees: where the image centre points.
        """
        fx = (width / 2) / math.tan(math.radians(hfov_deg) / 2)
        fy = fx if vfov_deg is None else (height / 2) / math.tan(math.radians(vfov_deg) / 2)
        return cls(width, height, fx, fy, width / 2, height / 2,
                   rotation=rotation_from_orientation(*orientation))

    @classmethod
    def from_opencv(cls, camera_matrix, distortion, width: int, height: int,
                    orientation=(0.0, 0.0, 0.0)) -> "Camera":
        """With the result of cv2.calibrateCamera (3x3 camera matrix, distortion coefficients)."""
        k = np.asarray(camera_matrix, float)
        d = tuple(np.asarray(distortion, float).ravel()[:5]) + (0.0,) * max(0, 5 - np.size(distortion))
        return cls(width, height, k[0, 0], k[1, 1], k[0, 2], k[1, 2], d,
                   rotation_from_orientation(*orientation))

    def _undistort(self, xd: float, yd: float, iterations: int = 20) -> tuple[float, float]:
        """Normalised distorted coordinates -> undistorted (iterative, like cv2.undistortPoints)."""
        k1, k2, p1, p2, k3 = self.distortion
        if not any(self.distortion):
            return xd, yd
        x, y = xd, yd
        for _ in range(iterations):
            r2 = x * x + y * y
            radial = 1 + k1 * r2 + k2 * r2 ** 2 + k3 * r2 ** 3
            dx = 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
            dy = p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
            x, y = (xd - dx) / radial, (yd - dy) / radial
        return x, y

    def camera_ray(self, u: float, v: float) -> np.ndarray:
        """Pixel -> unit vector in the camera frame."""
        x, y = (u - self.cx) / self.fx, (v - self.cy) / self.fy
        if self.division:
            f = 1.0 / (1.0 + self.division * (x * x + y * y))
            x, y = x * f, y * f
        x, y = self._undistort(x, y)
        s = np.array([x, y, 1.0])
        return s / np.linalg.norm(s)

    def pixel_to_ray(self, u: float, v: float) -> np.ndarray:
        """Pixel -> unit vector in the base frame of the platform."""
        return self.rotation @ self.camera_ray(u, v)

    def pixel_to_pan_tilt(self, u: float, v: float) -> tuple[float, float]:
        """Pixel -> (pan, tilt) in degrees the platform has to turn to."""
        return ray_to_pan_tilt(self.pixel_to_ray(u, v))

    def pan_tilt_to_pixel(self, pan_deg: float, tilt_deg: float):
        """Inverse (ignores OpenCV distortion): where in the image is (pan, tilt)? None if behind the camera."""
        s = self.rotation.T @ direction(pan_deg, tilt_deg)
        if s[2] <= 0:
            return None
        x, y = s[0] / s[2], s[1] / s[2]
        if self.division:
            # solve r_u = r_d / (1 + division * r_d^2) for r_d
            ru = math.hypot(x, y)
            d = 1 - 4 * self.division * ru * ru
            if ru > 1e-12:
                if d < 0:
                    return None                       # outside what the lens can show
                rd = (1 - math.sqrt(d)) / (2 * self.division * ru)
                x, y = x * rd / ru, y * rd / ru
        return self.cx + self.fx * x, self.cy + self.fy * y


def calibrate_camera(camera: Camera, measurements, fov: bool = True, distortion: bool = True) -> dict:
    """Calibration of a fixed camera from measurements (u, v, pan, tilt).

    Always estimates the rotation (orientation of the camera). Optionally also:
      fov:         the focal length, in case the datasheet field of view is wrong
      distortion:  the edge distortion (Camera.division); wide-angle webcams bend the image edges
    The search uses a grid that gets finer each round; for every grid point the
    rotation comes from the Kabsch algorithm. The starting point is always part of
    the grid, so the result is never worse than the rotation alone.

    Returns a dict with rotation, fx, fy, division, error (mean), errors_per_point,
    error_rotation_only (for comparison) and hfov_deg.
    """
    measurements = [tuple(map(float, m)) for m in measurements]
    if len(measurements) < 3:
        raise ValueError("at least 3 measurements needed")
    corner = (camera.width / 2 / camera.fx) ** 2 + (camera.height / 2 / camera.fy) ** 2

    def evaluate(log_factor: float, division: float):
        factor = math.exp(log_factor)
        # the image corner must stay inside what the model can show, otherwise it flips at the edge
        if 1 + division * corner / factor ** 2 < 0.25:
            return math.inf, None, None, None
        k = Camera(camera.width, camera.height, camera.fx * factor, camera.fy * factor,
                   camera.cx, camera.cy, camera.distortion, division=division)
        pairs = [(k.camera_ray(u, v), (p, t)) for u, v, p, t in measurements]
        r = calibrate_rotation(pairs)
        return mean_angle_error_deg(r, pairs), r, pairs, k

    best = (evaluate(0.0, camera.division)[0], 0.0, camera.division)    # (error, log(factor), division)
    error_start = best[0]
    width_f = 0.4 if fov else 0.0
    width_d = 0.3 if distortion else 0.0
    for _ in range(6):
        _, lf0, d0 = best
        for lf in np.linspace(lf0 - width_f, lf0 + width_f, 11 if width_f else 1):
            for d in np.linspace(d0 - width_d, d0 + width_d, 11 if width_d else 1):
                error = evaluate(float(lf), float(d))[0]
                if error < best[0] - 1e-12:
                    best = (error, float(lf), float(d))
        width_f, width_d = width_f / 3, width_d / 3
    error, r, pairs, k = evaluate(best[1], best[2])
    return {
        "rotation": r, "fx": k.fx, "fy": k.fy, "division": k.division,
        "error": error, "errors_per_point": angle_errors_deg(r, pairs),
        "error_rotation_only": error_start,
        "hfov_deg": math.degrees(2 * math.atan(camera.width / 2 / k.fx)),
    }


# ---------------------------------------------------------------------------
# Several fixed cameras
# ---------------------------------------------------------------------------

class CameraSystem:
    """All fixed cameras, addressed by the camera_id of the event.

    Example with two webcams pointing 30 degrees to the left and right:
        system = CameraSystem({
            "cam-1": Camera.from_fov(1920, 1080, 92, orientation=(-30, 15)),
            "cam-2": Camera.from_fov(1920, 1080, 92, orientation=(30, 15)),
        })
        pan, tilt = system.target_from_event(event)
    """

    def __init__(self, cameras: dict):
        if not cameras:
            raise ValueError("at least one camera needed")
        self.cameras = dict(cameras)

    def pan_tilt(self, camera_id: str, u: float, v: float) -> tuple[float, float]:
        if camera_id not in self.cameras:
            raise KeyError(f"unknown camera {camera_id!r}, known: {sorted(self.cameras)}")
        return self.cameras[camera_id].pixel_to_pan_tilt(u, v)

    def target_from_event(self, event: dict) -> tuple[float, float]:
        """One detection event (camera_id + bbox) -> (pan, tilt)."""
        return self.pan_tilt(event["camera_id"], *bbox_center(event["bbox"]))

    def target_from_events(self, events) -> tuple[float, float]:
        """Several simultaneous detections of the same drone (e.g. in the overlap of
        both webcams) -> one common direction, weighted by confidence.

        Allowed because all cameras sit close together and the drone is far away
        (error roughly distance between cameras / distance to the drone).
        """
        total = np.zeros(3)
        for e in events:
            camera = self.cameras[e["camera_id"]]
            total += e.get("confidence", 1.0) * camera.pixel_to_ray(*bbox_center(e["bbox"]))
        if not np.any(total):
            raise ValueError("no usable detections")
        return ray_to_pan_tilt(total)

    def sees(self, pan_deg: float, tilt_deg: float) -> list[str]:
        """Which cameras have the direction (pan, tilt) in their image? Useful for planning."""
        hits = []
        for cid, k in self.cameras.items():
            px = k.pan_tilt_to_pixel(pan_deg, tilt_deg)
            if px and 0 <= px[0] < k.width and 0 <= px[1] < k.height:
                hits.append(cid)
        return hits


# ---------------------------------------------------------------------------
# Platform: geometric angles -> servo angles
# ---------------------------------------------------------------------------

@dataclass
class Axis:
    """One servo axis. center = servo angle at geometric 0 degrees."""
    center: float = 90.0
    direction: int = 1          # +1 or -1, depending on how the servo is mounted
    minimum: float = 0.0
    maximum: float = 180.0

    def to_servo(self, deg: float) -> float:
        return max(self.minimum, min(self.maximum, self.center + self.direction * deg))

    def from_servo(self, servo_deg: float) -> float:
        return (servo_deg - self.center) * self.direction


@dataclass
class Platform:
    pan: Axis = field(default_factory=Axis)
    tilt: Axis = field(default_factory=Axis)

    def servo_angles(self, pan_deg: float, tilt_deg: float) -> tuple[float, float]:
        return self.pan.to_servo(pan_deg), self.tilt.to_servo(tilt_deg)

    def move_command(self, pan_deg: float, tilt_deg: float) -> str:
        """Command in the protocol of the Pico firmware (pico/main.py)."""
        sp, st = self.servo_angles(pan_deg, tilt_deg)
        return f"MOVE {sp:.1f} {st:.1f}"

    def clamp(self, pan_deg: float, tilt_deg: float) -> tuple[float, float]:
        """Nearest reachable direction: every axis up to its limit."""
        sp, st = self.servo_angles(pan_deg, tilt_deg)       # to_servo already clamps
        return self.pan.from_servo(sp), self.tilt.from_servo(st)

    def reachable(self, pan_deg: float, tilt_deg: float) -> bool:
        """False if at least one axis would hit its limit."""
        for axis, deg in ((self.pan, pan_deg), (self.tilt, tilt_deg)):
            raw = axis.center + axis.direction * deg
            if not axis.minimum <= raw <= axis.maximum:
                return False
        return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Pixel of a fixed camera -> pan/tilt")
    ap.add_argument("u", type=float)
    ap.add_argument("v", type=float)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--hfov", type=float, default=92, help="horizontal field of view in degrees")
    ap.add_argument("--pan", type=float, default=0, help="where the camera centre points: pan")
    ap.add_argument("--tilt", type=float, default=0, help="where the camera centre points: tilt")
    args = ap.parse_args()
    cam = Camera.from_fov(args.width, args.height, args.hfov, orientation=(args.pan, args.tilt))
    pan, tilt = cam.pixel_to_pan_tilt(args.u, args.v)
    print(f"pan {pan:+.2f} deg, tilt {tilt:+.2f} deg")


if __name__ == "__main__":
    main()
