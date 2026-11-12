# Pan-Tilt-Firmware v2 fuer Raspberry Pi Pico 2 W (MicroPython)
# Befehle per USB-Serial, je eine Zeile:
#   MOVE <pan> <tilt>   Zielwinkel in Grad anfahren (sanft, mit SPEED)  -> OK
#   SPEED <grad_pro_s>  Hoechstgeschwindigkeit setzen (1-600)           -> OK
#   HOME                zurueck in die Mitte                            -> OK
#   STOP                an der aktuellen Position anhalten              -> OK
#   POS?                aktuelle Position                               -> POS <pan> <tilt>
# Unbekannte oder fehlerhafte Befehle -> ERR

from machine import Pin, PWM
import sys, select, time

MIN_US, MAX_US = 600, 2400     # Pulsgrenzen (MS18: 500-2500), beim Kalibrieren anpassen
PAN_PIN, TILT_PIN = 15, 14
PAN_LIMIT = (0, 180)
TILT_LIMIT = (0, 180)          # nach dem Einbau auf den echten Bereich setzen, z.B. (80, 180)
HOME_POS = (90, 90)
TAKT_MS = 20                   # 50 Hz, wie die Servo-Periode


class Achse:
    def __init__(self, pin, limits, start):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(50)
        self.limits = limits
        self.ist = self.ziel = self.begrenzen(start)
        self.schreiben()

    def begrenzen(self, grad):
        return max(self.limits[0], min(self.limits[1], grad))

    def setze_ziel(self, grad):
        self.ziel = self.begrenzen(grad)

    def schritt(self, max_schritt):
        diff = self.ziel - self.ist
        if diff:
            self.ist += max(-max_schritt, min(max_schritt, diff))
            self.schreiben()

    def schreiben(self):
        us = MIN_US + (MAX_US - MIN_US) * self.ist / 180
        self.pwm.duty_ns(int(us * 1000))


pan = Achse(PAN_PIN, PAN_LIMIT, HOME_POS[0])
tilt = Achse(TILT_PIN, TILT_LIMIT, HOME_POS[1])
speed = 60.0                   # Grad pro Sekunde; langsam starten, die Kamera ist schwer


def befehl(zeile):
    global speed
    teile = zeile.split()
    if not teile:
        return None
    cmd = teile[0].upper()
    try:
        if cmd == "MOVE" and len(teile) == 3:
            pan.setze_ziel(float(teile[1]))
            tilt.setze_ziel(float(teile[2]))
            return "OK"
        if cmd == "SPEED" and len(teile) == 2:
            speed = max(1.0, min(600.0, float(teile[1])))
            return "OK"
        if cmd == "HOME" and len(teile) == 1:
            pan.setze_ziel(HOME_POS[0])
            tilt.setze_ziel(HOME_POS[1])
            return "OK"
        if cmd == "STOP" and len(teile) == 1:
            pan.ziel, tilt.ziel = pan.ist, tilt.ist
            return "OK"
        if cmd == "POS?" and len(teile) == 1:
            return "POS %.1f %.1f" % (pan.ist, tilt.ist)
    except ValueError:
        pass
    return "ERR"


poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
puffer = ""
naechster = time.ticks_ms()

while True:
    # Eingabe Zeichen fuer Zeichen lesen, damit die Bewegung nie blockiert
    if poll.poll(0):
        z = sys.stdin.read(1)
        if z in ("\r", "\n"):
            antwort = befehl(puffer)
            if antwort:
                print(antwort)
            puffer = ""
        elif z:
            puffer += z

    # Alle 20 ms ein kleines Stueck Richtung Ziel fahren
    if time.ticks_diff(time.ticks_ms(), naechster) >= 0:
        naechster = time.ticks_add(naechster, TAKT_MS)
        max_schritt = speed * TAKT_MS / 1000
        pan.schritt(max_schritt)
        tilt.schritt(max_schritt)
