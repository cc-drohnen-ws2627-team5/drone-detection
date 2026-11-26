"""Tests for angles.py. Run: python3 -m pytest tests"""
import math

import numpy as np
import pytest

from angles import (Axis, Camera, CameraSystem, Platform, calibrate_camera, calibrate_rotation,
                    direction, mean_angle_error_deg, ray_to_pan_tilt, rotation_from_orientation)


def test_direction_and_back():
    for pan, tilt in [(0, 0), (30, 25), (-120, 10), (45, 80)]:
        assert ray_to_pan_tilt(direction(pan, tilt)) == pytest.approx((pan, tilt))


def test_image_centre_points_to_orientation():
    cam = Camera.from_fov(1920, 1080, 60, orientation=(30, 25))
    assert cam.pixel_to_pan_tilt(960, 540) == pytest.approx((30, 25))


def test_right_and_up_in_the_image():
    cam = Camera.from_fov(1920, 1080, 60)
    pan, tilt = cam.pixel_to_pan_tilt(1920, 540)
    assert pan == pytest.approx(30) and tilt == pytest.approx(0)          # right edge = half the fov
    pan, tilt = cam.pixel_to_pan_tilt(960, 0)
    assert pan == pytest.approx(0) and tilt > 15                          # top = up


def test_pixel_and_back_with_distortion():
    cam = Camera.from_fov(1920, 1080, 92, orientation=(-20, 15, 2))
    cam.division = -0.1
    for u, v in [(100, 100), (960, 540), (1800, 900)]:
        assert cam.pan_tilt_to_pixel(*cam.pixel_to_pan_tilt(u, v)) == pytest.approx((u, v), abs=1e-6)


def test_kabsch_finds_the_rotation():
    true = rotation_from_orientation(-33, 22, 1)
    cam = Camera.from_fov(1920, 1080, 60)
    pairs = [(cam.camera_ray(u, v), ray_to_pan_tilt(true @ cam.camera_ray(u, v)))
             for u, v in [(100, 100), (1800, 150), (960, 540), (200, 950), (1700, 900)]]
    r = calibrate_rotation(pairs)
    assert np.allclose(r, true, atol=1e-9) and mean_angle_error_deg(r, pairs) < 1e-6
    with pytest.raises(ValueError):
        calibrate_rotation(pairs[:2])


def test_calibration_finds_fov_and_edge_distortion():
    # real webcam: 100 degrees instead of the 92 entered, with barrel distortion
    true = Camera.from_fov(1920, 1080, 100, orientation=(-3, 18, 1))
    true.division = -0.12
    pixels = [(200, 180), (1720, 200), (960, 540), (250, 900), (1680, 880), (960, 150)]
    measurements = [(u, v, *true.pixel_to_pan_tilt(u, v)) for u, v in pixels]
    res = calibrate_camera(Camera.from_fov(1920, 1080, 92), measurements)
    assert res["error_rotation_only"] > 4 and res["error"] < 0.05
    assert res["hfov_deg"] == pytest.approx(100, abs=0.5)
    assert res["division"] == pytest.approx(-0.12, abs=0.01)
    k = Camera(1920, 1080, res["fx"], res["fy"], 960, 540, rotation=res["rotation"], division=res["division"])
    for u, v in [(60, 60), (1860, 1020), (1400, 540)]:              # pixels not used for calibrating
        angle = math.degrees(math.acos(np.clip(k.pixel_to_ray(u, v) @ true.pixel_to_ray(u, v), -1, 1)))
        assert angle < 0.1


def test_two_webcams_and_overlap():
    system = CameraSystem({"cam-1": Camera.from_fov(1920, 1080, 60, orientation=(-30, 20)),
                           "cam-2": Camera.from_fov(1920, 1080, 60, orientation=(30, 20))})
    event = {"camera_id": "cam-2", "bbox": {"x": 940, "y": 530, "w": 40, "h": 20}}
    assert system.target_from_event(event) == pytest.approx((30, 20))
    assert system.sees(0, 20) == ["cam-1", "cam-2"] and system.sees(-50, 20) == ["cam-1"]
    with pytest.raises(KeyError):
        system.pan_tilt("cam-9", 1, 2)


def test_platform_with_our_measured_axes():
    p = Platform(pan=Axis(center=90, direction=-1), tilt=Axis(center=180, direction=-1, minimum=90))
    assert p.move_command(0, 0) == "MOVE 90.0 180.0"       # straight ahead, level
    assert p.move_command(30, 90) == "MOVE 60.0 90.0"      # 30 deg right, straight up
    assert p.reachable(-90, 45) and not p.reachable(0, -5)
    assert p.clamp(120, -20) == (90, 0)
