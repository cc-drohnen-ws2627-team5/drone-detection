"""Tests for pantilt_control.py without a Pico. Run: python3 -m pytest tests"""
import json
from collections import namedtuple

import numpy as np
import pytest

from angles import Axis, Camera, Platform, ray_to_pan_tilt, rotation_from_orientation
from pantilt_control import Controller, find_pico


class FakePico:
    """Records the commands and answers like the firmware."""

    def __init__(self):
        self.commands = []
        self.servo = (90.0, 90.0)
        self._answer = b"OK\r\n"

    def reset_input_buffer(self):
        pass

    def write(self, data):
        cmd = data.decode().strip()
        self.commands.append(cmd)
        if cmd == "POS?":
            self._answer = ("POS %.1f %.1f\r\n" % self.servo).encode()
        else:
            if cmd.startswith("MOVE"):
                self.servo = tuple(float(x) for x in cmd.split()[1:])
            self._answer = b"OK\r\n"

    def readline(self):
        return self._answer


def new_controller(tmp_path, **kw):
    cameras = {
        "cam-1": Camera.from_fov(1920, 1080, 60, orientation=(-30, 25)),
        "cam-2": Camera.from_fov(1920, 1080, 60, orientation=(30, 25)),
    }
    platform = Platform(pan=Axis(center=90), tilt=Axis(center=90))
    return Controller(FakePico(), cameras, platform, tmp_path / "calibration.json", **kw)


def test_step_sends_move(tmp_path):
    ctl = new_controller(tmp_path)
    assert ctl.step(5, -2) == "OK"
    assert ctl.ser.commands[-1] == "MOVE 95.0 88.0"


def test_target_from_webcam_pixel(tmp_path):
    ctl = new_controller(tmp_path)
    assert "OK" in ctl.target("cam-2 960 540")              # image centre of cam-2
    assert ctl.ser.commands[-1] == "MOVE 120.0 115.0"       # pan +30, tilt +25


def test_unreachable_target_is_not_sent(tmp_path):
    ctl = new_controller(tmp_path)
    before = list(ctl.ser.commands)
    assert "out of range" in ctl.move(120, 0)
    assert ctl.ser.commands == before


@pytest.mark.parametrize("text", ["cam-1 960", "cam-7 1 2", "cam-1 a b"])
def test_wrong_input(tmp_path, text):
    with pytest.raises(ValueError):
        new_controller(tmp_path).target(text)


def test_calibration_saves_and_loads(tmp_path):
    ctl = new_controller(tmp_path)
    true = Camera.from_fov(1920, 1080, 75, orientation=(-28, 22, 1))
    true.division = -0.1
    for u, v in [(200, 180), (1720, 200), (960, 540), (250, 900), (1680, 880), (960, 150)]:
        ctl.move(*true.pixel_to_pan_tilt(u, v))             # HQ camera points at the landmark
        ctl.add_point(f"cam-1 {u} {v}")
    ctl.add_point("cam-1 5 5")                              # wrong click ...
    assert "6 left" in ctl.delete_point("cam-1")            # ... deleted again
    assert "no points" in ctl.delete_point("cam-2")
    message = ctl.calibrate()
    assert "cam-1: error 0.0" in message and "field of view 75 deg" in message and "cam-2: 0/3" in message
    data = json.loads((tmp_path / "calibration.json").read_text())
    assert set(data) == {"cam-1"} and len(data["cam-1"]["points"]) == 6
    again = new_controller(tmp_path)
    assert "cam-1" in again.message
    assert again.system.cameras["cam-1"].division == pytest.approx(-0.1, abs=0.01)


def test_reads_files_of_the_german_version(tmp_path):
    r = rotation_from_orientation(-28, 22)
    (tmp_path / "kalibrierung.json").write_text(json.dumps({
        "cam-1": r.tolist(),                                                        # oldest format
        "cam-2": {"rotation": r.tolist(), "fx": 900.0, "fy": 900.0, "rand": -0.05, "punkte": []},
    }))
    ctl = new_controller(tmp_path)
    assert "cam-1, cam-2" in ctl.message
    assert np.allclose(ctl.system.cameras["cam-1"].rotation, r)
    assert ctl.system.cameras["cam-2"].division == -0.05 and ctl.system.cameras["cam-2"].fx == 900


def test_find_pico():
    P = namedtuple("P", "device vid")
    assert find_pico("COM7") == "COM7"                                     # explicit port wins
    assert find_pico(None, [P("/dev/ttyS0", None), P("/dev/ttyACM0", 0x2E8A)]) == "/dev/ttyACM0"
    mac = [P("/dev/tty.usbmodem1101", 0x2E8A), P("/dev/cu.usbmodem1101", 0x2E8A), P("/dev/cu.Bluetooth", None)]
    assert find_pico(None, mac) == "/dev/cu.usbmodem1101"
    with pytest.raises(RuntimeError):
        find_pico(None, [P("/dev/ttyS0", None)])
