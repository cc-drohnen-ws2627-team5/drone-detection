"""Tests for pantilt_click.py without windows and cameras. Run: python3 -m pytest tests"""
import numpy as np
import pytest

from angles import Camera, rotation_from_orientation, ray_to_pan_tilt
from pantilt_click import ClickControl, camera_pixel_to_window, window_to_camera_pixel
from pantilt_hq import hq_display
from test_pantilt_control import new_controller


def test_click_in_scaled_window():
    k = Camera.from_fov(1920, 1080, 60)
    assert window_to_camera_pixel(480, 270, (1920, 1080), (960, 540), k) == (960, 540)
    assert window_to_camera_pixel(480, 270, (1280, 720), (960, 540), k) == pytest.approx((960, 540))
    assert camera_pixel_to_window(960, 540, (960, 540), k) == (480, 270)


def test_click_in_aim_mode_moves_platform(tmp_path):
    app = ClickControl(new_controller(tmp_path))
    app.click("cam-2", 960, 540)
    assert app.ctl.ser.commands[-1] == "MOVE 120.0 115.0"


def test_calibrate_by_clicking(tmp_path):
    app = ClickControl(new_controller(tmp_path))
    true = rotation_from_orientation(-33, 22, 1)
    k = app.ctl.system.cameras["cam-1"]
    app.key("m")
    assert app.mode == "CALIBRATE"
    for u, v in [(150, 150), (1750, 200), (960, 540), (300, 950), (1650, 900)]:
        app.ctl.move(*ray_to_pan_tilt(true @ k.camera_ray(u, v)))     # HQ camera points at the landmark
        before = list(app.ctl.ser.commands)
        app.click("cam-1", u, v)                                       # same landmark in the webcam image
        assert app.ctl.ser.commands == before                          # platform stays
    app.key("c")
    assert "cam-1: error 0.0" in app.ctl.message
    app.key("m")
    app.click("cam-1", 1200, 300)                                      # now an aim click hits
    assert (app.ctl.pan, app.ctl.tilt) == pytest.approx(ray_to_pan_tilt(true @ k.camera_ray(1200, 300)), abs=0.05)


def test_keys(tmp_path):
    app = ClickControl(new_controller(tmp_path))
    app.key("d"); app.key("w")
    assert (app.ctl.pan, app.ctl.tilt) == (2, 2)
    app.key("+"); app.key("a")
    assert app.ctl.pan == -2
    app.key("h")
    assert (app.ctl.pan, app.ctl.tilt) == (0, 0)
    assert app.key("q") is False and app.key("\x1b") is False


def test_error_is_shown_instead_of_crash(tmp_path):
    assert ClickControl(new_controller(tmp_path)).click("cam-7", 1, 2).startswith("Error")


def test_drawing(tmp_path):
    app = ClickControl(new_controller(tmp_path))
    app.ctl.move(30, 25)                                               # image centre of cam-2
    img = np.zeros((540, 960, 3), np.uint8)
    app.overlay(img, "cam-2")
    assert img[270, 480 + 14 - 1:480 + 14 + 2, 2].max() == 255         # red circle around the centre
    assert hq_display(np.zeros((760, 1014, 3), np.uint8), (100, 100)).any()
