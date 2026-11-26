# Pan-tilt firmware v4 for the Raspberry Pi Pico 2 W (MicroPython)
# Commands over USB serial, one per line:
#   MOVE <pan> <tilt>   go to the target angles in degrees (smoothly, see SPEED)  -> OK
#   SPEED <deg_per_s>   set the maximum speed (1-600)                              -> OK
#   ACCEL <deg_per_s2>  set the acceleration (10-5000); small = softer             -> OK
#   KICK <pan> <tilt>   start-up help in degrees per axis, 0 = off                 -> OK
#   HOME                back to the centre                                         -> OK
#   STOP                brake softly and stay                                      -> OK
#   POS?                current position                                           -> POS <pan> <tilt>
# Unknown or broken commands -> ERR
# Angles are servo angles 0-180. On our platform: pan 90 = straight ahead, larger = left;
# tilt 90 = straight up, 180 = level to the front, 0 = level to the back.
#
# Start-up help (new in v4): a servo pushes harder the further it is from its target.
# When it starts smoothly, it is only a tiny bit away from the target at first, and
# when lifting the heavy camera the force is not enough to get going. That is why the
# tilt servo gets a target a few degrees further away for KICK_MS when it starts to
# lift, like a small push by hand. Turn it off with KICK 0 0.

from machine import Pin, PWM
import sys, select, time

MIN_US, MAX_US = 600, 2400     # pulse limits (MS18: 500-2500)
PAN_PIN, TILT_PIN = 15, 14
PAN_LIMIT = (0, 180)
TILT_LIMIT = (0, 180)
HOME_POS = (90, 90)            # lens pointing straight up: the servo carries the least load there
PERIOD_MS = 20                 # 50 Hz, like the servo period
TILT_VERTICAL = 90             # servo angle at which the camera points straight up
KICK_PAN, KICK_TILT = 0.0, 6.0 # start-up help in degrees (pan does not need it)
KICK_MS = 150                  # how long the push lasts


class Axis:
    def __init__(self, pin, limits, start, kick=0.0, vertical=None):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(50)
        self.limits = limits
        self.pos = self.target = self.clamp(start)
        self.v = 0.0               # current speed in degrees per second
        self.kick = kick           # size of the push in degrees, 0 = off
        self.vertical = vertical   # None: push in both directions, otherwise only when lifting
        self.kick_offset = 0.0
        self.kick_until = time.ticks_ms()
        self.write()

    def clamp(self, deg):
        return max(self.limits[0], min(self.limits[1], deg))

    def set_target(self, deg):
        self.target = self.clamp(deg)

    def lifts(self):
        # Does the axis move against gravity, i.e. towards vertical?
        if self.vertical is None:
            return True
        return abs(self.target - self.vertical) < abs(self.pos - self.vertical)

    def kick_over(self):
        return time.ticks_diff(self.kick_until, time.ticks_ms()) <= 0

    def step(self, v_max, a, dt):
        # Soft start and soft stop: the speed changes by at most a*dt per period,
        # and braking starts in time before the target.
        diff = self.target - self.pos
        if diff == 0 and self.v == 0:
            if self.kick_offset and self.kick_over():
                self.kick_offset = 0.0
                self.write()
            return
        if self.v == 0 and self.kick and abs(diff) > 0.2 and self.lifts():
            # starting from standstill: short push in the direction of travel,
            # for small moves at most twice as far as the move itself
            size = min(self.kick, max(1.5, 2 * abs(diff)))
            self.kick_offset = size if diff > 0 else -size
            self.kick_until = time.ticks_add(time.ticks_ms(), KICK_MS)
        elif self.kick_offset and self.kick_over():
            self.kick_offset = 0.0
        dv = a * dt
        # highest speed from which we can still stop at the target
        v_goal = min(v_max, ((dv / 2) ** 2 + 2 * a * abs(diff)) ** 0.5 - dv / 2)
        if diff < 0:
            v_goal = -v_goal
        self.v += max(-dv, min(dv, v_goal - self.v))
        way = self.v * dt
        if way * diff > 0 and abs(way) >= abs(diff) or abs(diff) < 0.02 and abs(self.v) <= dv:
            self.pos, self.v = self.target, 0.0          # arrived
        else:
            self.pos = self.clamp(self.pos + way)
        self.write()

    def brake(self, a):
        # set the target so that the axis rolls out with a instead of stopping hard
        self.target = self.clamp(self.pos + self.v * abs(self.v) / (2 * a))

    def write(self):
        deg = self.clamp(self.pos + self.kick_offset)
        us = MIN_US + (MAX_US - MIN_US) * deg / 180
        self.pwm.duty_ns(int(us * 1000))


pan = Axis(PAN_PIN, PAN_LIMIT, HOME_POS[0], kick=KICK_PAN)
tilt = Axis(TILT_PIN, TILT_LIMIT, HOME_POS[1], kick=KICK_TILT, vertical=TILT_VERTICAL)
speed = 60.0                   # degrees per second; start slowly, the camera is heavy
accel = 200.0                  # degrees per second^2; smaller = softer start and stop


def command(line):
    global speed, accel
    parts = line.split()
    if not parts:
        return None
    cmd = parts[0].upper()
    try:
        if cmd == "MOVE" and len(parts) == 3:
            pan.set_target(float(parts[1]))
            tilt.set_target(float(parts[2]))
            return "OK"
        if cmd == "SPEED" and len(parts) == 2:
            speed = max(1.0, min(600.0, float(parts[1])))
            return "OK"
        if cmd == "ACCEL" and len(parts) == 2:
            accel = max(10.0, min(5000.0, float(parts[1])))
            return "OK"
        if cmd == "KICK" and len(parts) == 3:
            pan.kick = max(0.0, min(20.0, float(parts[1])))
            tilt.kick = max(0.0, min(20.0, float(parts[2])))
            return "OK"
        if cmd == "HOME" and len(parts) == 1:
            pan.set_target(HOME_POS[0])
            tilt.set_target(HOME_POS[1])
            return "OK"
        if cmd == "STOP" and len(parts) == 1:
            pan.brake(accel)
            tilt.brake(accel)
            return "OK"
        if cmd == "POS?" and len(parts) == 1:
            return "POS %.1f %.1f" % (pan.pos, tilt.pos)
    except ValueError:
        pass
    return "ERR"


poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
buffer = ""
next_tick = time.ticks_ms()

while True:
    # read input character by character so the movement never blocks
    if poll.poll(0):
        c = sys.stdin.read(1)
        if c in ("\r", "\n"):
            answer = command(buffer)
            if answer:
                print(answer)
            buffer = ""
        elif c:
            buffer += c

    # every 20 ms move a small step towards the target
    if time.ticks_diff(time.ticks_ms(), next_tick) >= 0:
        next_tick = time.ticks_add(next_tick, PERIOD_MS)
        pan.step(speed, accel, PERIOD_MS / 1000)
        tilt.step(speed, accel, PERIOD_MS / 1000)
