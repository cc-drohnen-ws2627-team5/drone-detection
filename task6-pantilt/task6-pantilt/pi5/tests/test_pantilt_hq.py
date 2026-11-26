"""Tests for stage 2 (pantilt_hq.py) without cameras and Pico. Run: python3 -m pytest tests"""
import math

import numpy as np
import pytest

from angles import Axis, Camera, Platform
from pantilt_hq import ColorDetector, FineControl, SkyDetector, current_position, pan_tilt_in_hq_image
from test_pantilt_control import new_controller

PX_PER_DEG = 1014 / 22.2          # roughly, in the image centre


def test_direction_in_hq_image():
    assert pan_tilt_in_hq_image(507, 380, 10, 20) == pytest.approx((10, 20))
    pan, tilt = pan_tilt_in_hq_image(507 + 5 * PX_PER_DEG, 380, 0, 0)
    assert pan == pytest.approx(5, abs=0.1) and tilt == pytest.approx(0, abs=1e-6)   # right = more pan
    _, tilt = pan_tilt_in_hq_image(507, 380 - 3 * PX_PER_DEG, 0, 30)
    assert tilt == pytest.approx(33, abs=0.1)                                         # up = more tilt


def test_fine_control_corrects_part_and_limits():
    f = FineControl(Platform(), gain=0.5, max_step_deg=4)
    pan, tilt = f.target(507 + 2 * PX_PER_DEG, 380, (0, 0))
    assert pan == pytest.approx(1, abs=0.05) and tilt == pytest.approx(0, abs=0.05)
    pan, _ = f.target(507 + 2 * PX_PER_DEG, 380, (0, 60))      # higher up the same image offset
    assert pan == pytest.approx(2, abs=0.1)                     # needs more pan (1 / cos(tilt))
    pan, _ = f.target(1000, 380, (0, 20))                       # far at the edge: at most 4 * 0.5
    assert pan == pytest.approx(2)


def test_current_position_from_pico(tmp_path):
    ctl = new_controller(tmp_path)
    ctl.ser.servo = (100.0, 120.0)                              # new_controller: centre 90, direction +1
    assert current_position(ctl) == pytest.approx((10, 30))
    ctl.ser.write = lambda d: None                              # Pico answers nonsense
    ctl.ser._answer = b"ERR\r\n"
    ctl.pan, ctl.tilt = 3, 4
    assert current_position(ctl) == (3, 4)                      # then the last command


def test_closed_loop_pulls_target_to_the_centre():
    """Webcam aims 4 degrees off, HQ camera mounted 1.5 degrees crooked, target moves:
    stage 2 still brings it to the image centre and keeps it there."""
    platform = Platform(pan=Axis(center=90, direction=-1), tilt=Axis(center=180, direction=-1, minimum=90))
    fine = FineControl(platform, gain=0.6)
    crooked = (1.5, -1.0)
    target = [20.0, 35.0]
    current = (target[0] - 4, target[1] + 3)                   # stage 1 is off
    errors = []
    for _ in range(40):
        target[0] += 0.3                                        # drone flies to the right
        view = Camera.from_fov(1014, 760, 22.2, 16.7, orientation=(current[0] + crooked[0], current[1] + crooked[1]))
        u, v = view.pan_tilt_to_pixel(*target)
        assert 0 <= u < 1014 and 0 <= v < 760                   # stays in the HQ image
        errors.append(math.hypot(u - 507, v - 380) / PX_PER_DEG)
        current = platform.clamp(*fine.target(u, v, current))
    assert errors[0] > 2.5 and max(errors[-10:]) < 0.7          # less than 1 degree from the centre


def test_color_detector_finds_red_object():
    img = np.full((760, 1014, 3), 180, np.uint8)
    img[300:340, 700:760] = (0, 0, 220)                         # red in BGR
    u, v = ColorDetector("red").image(img)
    assert u == pytest.approx(730, abs=4) and v == pytest.approx(320, abs=4)
    assert ColorDetector("blue").image(img) is None


def test_sky_detector_finds_dark_spot():
    y = np.linspace(200, 150, 760)[:, None, None]               # bright sky with a gradient
    rng = np.random.default_rng(0)
    img = np.clip(np.broadcast_to(y, (760, 1014, 3)) + rng.normal(0, 3, (760, 1014, 3)), 0, 255).astype(np.uint8)
    d = SkyDetector()
    assert d.image(img) is None                                  # empty sky: nothing
    img[400:412, 300:320] = 60                                   # small dark drone
    u, v = d.image(img)
    assert u == pytest.approx(310, abs=6) and v == pytest.approx(406, abs=6)
