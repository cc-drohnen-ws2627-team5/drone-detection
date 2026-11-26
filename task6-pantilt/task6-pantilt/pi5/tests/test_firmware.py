"""Tests for the Pico firmware (pico/main.py) on a computer, without a Pico.

machine and the MicroPython time functions are replaced by fakes, the endless
loop at the end of main.py is not run. Run: python3 -m pytest tests
"""
import sys
import types
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[2] / "pico" / "main.py"
PERIOD = 0.02


class Clock:
    ms = 0


def firmware():
    """Load main.py up to the endless loop, with fake machine and time modules."""
    machine = types.ModuleType("machine")

    class PWM:
        def __init__(self, pin):
            self.ns = None

        def freq(self, f):
            pass

        def duty_ns(self, ns):
            self.ns = ns

    machine.PWM, machine.Pin = PWM, lambda n: n
    fake_time = types.ModuleType("time")
    fake_time.ticks_ms = lambda: Clock.ms
    fake_time.ticks_add = lambda a, b: a + b
    fake_time.ticks_diff = lambda a, b: a - b
    old = {k: sys.modules.get(k) for k in ("machine", "time")}
    sys.modules["machine"], sys.modules["time"] = machine, fake_time
    try:
        source = MAIN.read_text().split("poll = select.poll()")[0]
        g = {"__name__": "firmware"}
        exec(compile(source, str(MAIN), "exec"), g)
    finally:
        for k, v in old.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return g


def servo_deg(axis):
    """Which angle does the servo get as a pulse right now?"""
    us = axis.pwm.ns / 1000
    return (us - 600) * 180 / (2400 - 600)


def run(g, seconds):
    trace = []
    for _ in range(round(seconds / PERIOD)):
        Clock.ms += 20
        g["pan"].step(g["speed"], g["accel"], PERIOD)
        g["tilt"].step(g["speed"], g["accel"], PERIOD)
        trace.append((g["tilt"].pos, servo_deg(g["tilt"])))
    return trace


@pytest.fixture
def g():
    Clock.ms = 0
    return firmware()


def test_start_and_pos(g):
    assert g["command"]("POS?") == "POS 90.0 90.0"
    assert servo_deg(g["tilt"]) == pytest.approx(90)


def test_push_when_lifting(g):
    g["command"]("MOVE 90 180")                 # first level to the front
    run(g, 4)
    assert g["tilt"].pos == 180 and servo_deg(g["tilt"]) == pytest.approx(180)
    g["command"]("MOVE 90 170")                 # lift by 10 degrees
    trace = run(g, 3)
    # for the first 150 ms the servo gets a target 6 degrees further up
    assert trace[0][1] == pytest.approx(trace[0][0] - 6, abs=0.01)
    assert trace[6][1] == pytest.approx(trace[6][0] - 6, abs=0.01)
    # then exactly the planned path again, and exactly at the target in the end
    assert trace[9][1] == pytest.approx(trace[9][0], abs=0.01)
    assert trace[-1] == pytest.approx((170, 170), abs=0.01)


def test_no_push_when_lowering_or_for_pan(g):
    g["command"]("MOVE 90 150")
    run(g, 4)
    g["command"]("MOVE 120 170")                # tilt goes down, pan turns
    trace = run(g, 0.1)
    assert all(abs(planned - pulse) < 0.01 for planned, pulse in trace)
    assert servo_deg(g["pan"]) == pytest.approx(g["pan"].pos, abs=0.01)


def test_small_move_small_push(g):
    g["command"]("MOVE 90 180")
    run(g, 4)
    g["command"]("MOVE 90 179.5")               # fine correction from the HQ image
    trace = run(g, 0.04)
    assert trace[0][0] - trace[0][1] == pytest.approx(1.5, abs=0.01)


def test_kick_off(g):
    assert g["command"]("KICK 0 0") == "OK"
    g["command"]("MOVE 90 180")
    run(g, 4)
    g["command"]("MOVE 90 170")
    assert all(abs(planned - pulse) < 0.01 for planned, pulse in run(g, 0.3))
    assert g["command"]("KICK x") == "ERR"


def test_other_commands(g):
    for c in ("SPEED 120", "ACCEL 300", "HOME", "STOP"):
        assert g["command"](c) == "OK"
    assert g["command"]("FOO") == "ERR" and g["command"]("") is None
