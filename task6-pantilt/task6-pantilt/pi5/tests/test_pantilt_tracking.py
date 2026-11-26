"""Tests for pantilt_tracking.py without Pico and cameras. Run: python3 -m pytest tests"""
import numpy as np
import pytest

from angles import Camera
from pantilt_tracking import MotionDetector, Tracker, parse_args
from test_pantilt_control import new_controller


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def event(u=960, v=540, cid="cam-2", **extra):
    return {"camera_id": cid, "confidence": 0.9, "class": "drone",
            "bbox": {"x": u - 20, "y": v - 10, "w": 40, "h": 20}, **extra}


@pytest.fixture
def tr(tmp_path):
    return Tracker(new_controller(tmp_path), clock=Clock())


def test_detection_moves_platform(tr):
    assert tr.event(event()) is None
    assert "OK" in tr.tick()
    assert tr.ctl.ser.commands[-1] == "MOVE 120.0 115.0"        # image centre cam-2: pan +30, tilt +25


def test_at_most_one_command_per_period_and_deadband(tr):
    tr.event(event()); tr.tick()
    n = len(tr.ctl.ser.commands)
    tr.event(event(1500, 300)); assert tr.tick() is None       # too early
    tr.clock.t += 0.11
    assert tr.tick() is not None and len(tr.ctl.ser.commands) == n + 1
    tr.clock.t += 0.11
    tr.event(event(1501, 300)); assert tr.tick() is None       # tiny change: no twitching


@pytest.mark.parametrize("e, reason", [
    ({"camera_id": "cam-2"}, "incomplete"),
    (event(cid="cam-9"), "unknown camera"),
    (event(confidence=0.1), "confidence"),
])
def test_unusable_events_are_ignored(tr, e, reason):
    assert reason in tr.event(e)
    assert tr.tick() is None


def test_class_filter(tmp_path):
    tr = Tracker(new_controller(tmp_path), classes=["drone"], clock=Clock())
    assert "class" in tr.event(event(**{"class": "bird"}))
    assert tr.event(event()) is None


def test_stays_with_the_same_drone(tr):
    tr.event(event(track_id=1)); tr.tick()
    assert "following track 1" in tr.event(event(300, 300, track_id=2))
    tr.clock.t += 0.5
    assert tr.event(event(1000, 500, track_id=1)) is None       # same drone: keep following
    tr.clock.t += 1.5                                           # drone 1 is gone
    assert tr.event(event(300, 300, track_id=2)) is None and tr.track == 2


def test_target_beyond_range_goes_to_the_limit(tr):
    tr.ctl.platform.pan.maximum = 130                           # pan only up to +40 degrees
    tr.event(event(1919, 0, cid="cam-2"))
    assert "OK" in tr.tick()
    assert tr.ctl.ser.commands[-1].startswith("MOVE 130.0")


def test_home_when_nothing_comes(tr):
    tr.event(event()); tr.tick()
    tr.clock.t += 11
    assert "home position" in tr.tick()
    assert tr.ctl.ser.commands[-1] == "MOVE 90.0 120.0"         # home = pan 0, tilt 30
    tr.clock.t += 1
    assert tr.tick() is None                                    # only once


def test_hq_has_priority_over_webcams(tr):
    tr.hq_target(12, 22)
    assert "OK" in tr.tick() and tr.ctl.ser.commands[-1] == "MOVE 102.0 112.0"
    assert tr.event(event()) == "HQ camera leads"               # webcam is less precise
    tr.clock.t += 0.6                                           # HQ camera lost the target
    assert tr.event(event()) is None and tr.source == "webcam"


def test_motion_detector_finds_moving_object():
    k = Camera.from_fov(1920, 1080, 92)
    m = MotionDetector("cam-1", k, warmup_frames=20)
    rng = np.random.default_rng(0)
    background = rng.integers(90, 110, (360, 640, 3), dtype=np.uint8)
    for _ in range(40):
        assert m.image(background.copy()) is None              # nothing moves
    img = background.copy()
    img[100:140, 400:460] = 255                                 # object appears
    e = m.image(img)
    u, v = e["bbox"]["x"] + e["bbox"]["w"] / 2, e["bbox"]["y"] + e["bbox"]["h"] / 2
    assert u == pytest.approx(430 * 3, abs=40) and v == pytest.approx(120 * 3, abs=40)   # in 1920x1080


def test_options():
    assert parse_args(["--hq-only", "--hq", "color"]).hq == "color"
    for wrong in (["--hq-only"], ["--motion", "--hq", "mqtt"], ["--hq-only", "--hq", "mqtt"]):
        with pytest.raises(SystemExit):
            parse_args(wrong)
