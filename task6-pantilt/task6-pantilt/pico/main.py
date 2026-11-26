# Pan-Tilt-Firmware v4 fuer Raspberry Pi Pico 2 W (MicroPython)
# Befehle per USB-Serial, je eine Zeile:
#   MOVE <pan> <tilt>   Zielwinkel in Grad anfahren (sanft, mit SPEED)  -> OK
#   SPEED <grad_pro_s>  Hoechstgeschwindigkeit setzen (1-600)           -> OK
#   ACCEL <grad_pro_s2> Beschleunigung setzen (10-5000); klein = weich  -> OK
#   KICK <pan> <tilt>   Anfahrhilfe in Grad je Achse, 0 = aus           -> OK
#   HOME                zurueck in die Mitte                            -> OK
#   STOP                weich abbremsen und stehen bleiben              -> OK
#   POS?                aktuelle Position                               -> POS <pan> <tilt>
# Unbekannte oder fehlerhafte Befehle -> ERR
# Winkel sind Servo-Winkel 0-180. Bei unserer Plattform: Pan 90 = geradeaus, groesser = links;
# Tilt 90 = senkrecht nach oben, 180 = waagerecht nach vorne, 0 = waagerecht nach hinten.
#
# Anfahrhilfe (neu in v4): Ein Servo drueckt umso staerker, je weiter er vom Ziel weg ist.
# Faehrt er sanft los, ist er anfangs nur ein winziges Stueck vom Ziel entfernt, und beim
# Anheben der schweren Kamera reicht die Kraft nicht zum Losfahren. Deshalb bekommt der
# Tilt-Servo beim Losfahren nach oben fuer KICK_MS ein Ziel ein paar Grad weiter weg,
# wie ein kleiner Stups von Hand. Ausschalten mit KICK 0 0.

from machine import Pin, PWM
import sys, select, time

MIN_US, MAX_US = 600, 2400     # Pulsgrenzen (MS18: 500-2500)
PAN_PIN, TILT_PIN = 15, 14
PAN_LIMIT = (0, 180)
TILT_LIMIT = (0, 180)
HOME_POS = (90, 90)            # Objektiv senkrecht nach oben: dort traegt der Servo am wenigsten Last
TAKT_MS = 20                   # 50 Hz, wie die Servo-Periode
TILT_SENKRECHT = 90            # Servo-Winkel, bei dem die Kamera senkrecht steht
KICK_PAN, KICK_TILT = 0.0, 6.0 # Anfahrhilfe in Grad (Pan braucht keine)
KICK_MS = 150                  # so lange dauert der Stups


class Achse:
    def __init__(self, pin, limits, start, kick=0.0, senkrecht=None):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(50)
        self.limits = limits
        self.ist = self.ziel = self.begrenzen(start)
        self.v = 0.0               # aktuelle Geschwindigkeit in Grad pro Sekunde
        self.kick = kick           # Groesse des Stups in Grad, 0 = aus
        self.senkrecht = senkrecht # None: Stups in beide Richtungen, sonst nur beim Anheben
        self.kick_versatz = 0.0
        self.kick_bis = time.ticks_ms()
        self.schreiben()

    def begrenzen(self, grad):
        return max(self.limits[0], min(self.limits[1], grad))

    def setze_ziel(self, grad):
        self.ziel = self.begrenzen(grad)

    def hebt(self):
        # Faehrt die Achse gegen die Schwerkraft, also Richtung senkrecht?
        if self.senkrecht is None:
            return True
        return abs(self.ziel - self.senkrecht) < abs(self.ist - self.senkrecht)

    def kick_vorbei(self):
        return time.ticks_diff(self.kick_bis, time.ticks_ms()) <= 0

    def schritt(self, v_max, a, dt):
        # Weich anfahren und weich bremsen: Die Geschwindigkeit aendert sich pro Takt
        # hoechstens um a*dt, und vor dem Ziel wird rechtzeitig abgebremst.
        diff = self.ziel - self.ist
        if diff == 0 and self.v == 0:
            if self.kick_versatz and self.kick_vorbei():
                self.kick_versatz = 0.0
                self.schreiben()
            return
        if self.v == 0 and self.kick and abs(diff) > 0.2 and self.hebt():
            # Losfahren aus dem Stand: kurzer Stups in Fahrtrichtung, bei kleinen
            # Bewegungen hoechstens doppelt so weit wie die Bewegung selbst
            groesse = min(self.kick, max(1.5, 2 * abs(diff)))
            self.kick_versatz = groesse if diff > 0 else -groesse
            self.kick_bis = time.ticks_add(time.ticks_ms(), KICK_MS)
        elif self.kick_versatz and self.kick_vorbei():
            self.kick_versatz = 0.0
        dv = a * dt
        # hoechste Geschwindigkeit, aus der man bis zum Ziel noch anhalten kann
        v_soll = min(v_max, ((dv / 2) ** 2 + 2 * a * abs(diff)) ** 0.5 - dv / 2)
        if diff < 0:
            v_soll = -v_soll
        self.v += max(-dv, min(dv, v_soll - self.v))
        weg = self.v * dt
        if weg * diff > 0 and abs(weg) >= abs(diff) or abs(diff) < 0.02 and abs(self.v) <= dv:
            self.ist, self.v = self.ziel, 0.0          # angekommen
        else:
            self.ist = self.begrenzen(self.ist + weg)
        self.schreiben()

    def bremsen(self, a):
        # Ziel so setzen, dass die Achse mit a ausrollt statt hart zu stoppen
        self.ziel = self.begrenzen(self.ist + self.v * abs(self.v) / (2 * a))

    def schreiben(self):
        grad = self.begrenzen(self.ist + self.kick_versatz)
        us = MIN_US + (MAX_US - MIN_US) * grad / 180
        self.pwm.duty_ns(int(us * 1000))


pan = Achse(PAN_PIN, PAN_LIMIT, HOME_POS[0], kick=KICK_PAN)
tilt = Achse(TILT_PIN, TILT_LIMIT, HOME_POS[1], kick=KICK_TILT, senkrecht=TILT_SENKRECHT)
speed = 60.0                   # Grad pro Sekunde; langsam starten, die Kamera ist schwer
accel = 200.0                  # Grad pro Sekunde^2; kleiner = weicheres Anfahren und Bremsen


def befehl(zeile):
    global speed, accel
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
        if cmd == "ACCEL" and len(teile) == 2:
            accel = max(10.0, min(5000.0, float(teile[1])))
            return "OK"
        if cmd == "KICK" and len(teile) == 3:
            pan.kick = max(0.0, min(20.0, float(teile[1])))
            tilt.kick = max(0.0, min(20.0, float(teile[2])))
            return "OK"
        if cmd == "HOME" and len(teile) == 1:
            pan.setze_ziel(HOME_POS[0])
            tilt.setze_ziel(HOME_POS[1])
            return "OK"
        if cmd == "STOP" and len(teile) == 1:
            pan.bremsen(accel)
            tilt.bremsen(accel)
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
        pan.schritt(speed, accel, TAKT_MS / 1000)
        tilt.schritt(speed, accel, TAKT_MS / 1000)
