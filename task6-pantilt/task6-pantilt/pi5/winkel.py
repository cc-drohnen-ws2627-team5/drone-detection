"""Winkelberechnung fuer das Pan-Tilt-Tracking (Task 6, Stufe 1).

Rechnet eine Erkennung in einer festen Kamera (Pixel u, v) in Pan- und
Tilt-Winkel der Plattform um und diese weiter in Servowinkel fuer den Pico.

Koordinatensysteme (wie OpenCV):
  Kamera:  x nach rechts, y nach unten, z in Blickrichtung
  Basis:   das System der Pan-Tilt-Plattform bei pan = 0, tilt = 0,
           ebenfalls x rechts, y unten, z nach vorn
  pan  > 0: nach rechts drehen,  tilt > 0: nach oben kippen

Ablauf:
  kamera = Kamera.aus_sichtfeld(1920, 1080, hfov_grad=60, ausrichtung=(30, 10))
  pan, tilt = kamera.pixel_zu_pan_tilt(1500, 400)
  befehl = plattform.move_befehl(pan, tilt)        # z. B. "MOVE 117.3 98.1"

Nur numpy wird gebraucht, kein OpenCV.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def richtung(pan_grad: float, tilt_grad: float) -> np.ndarray:
    """Einheitsvektor in Richtung (pan, tilt) im Basissystem."""
    p, t = math.radians(pan_grad), math.radians(tilt_grad)
    return np.array([math.cos(t) * math.sin(p), -math.sin(t), math.cos(t) * math.cos(p)])


def strahl_zu_pan_tilt(strahl) -> tuple[float, float]:
    """Richtungsvektor im Basissystem -> (pan, tilt) in Grad."""
    x, y, z = np.asarray(strahl, dtype=float)
    pan = math.degrees(math.atan2(x, z))
    tilt = math.degrees(math.atan2(-y, math.hypot(x, z)))
    return pan, tilt


def rotation_aus_ausrichtung(pan_grad: float, tilt_grad: float, roll_grad: float = 0.0) -> np.ndarray:
    """Drehmatrix Kamera -> Basis fuer eine Kamera, deren Bildmitte auf (pan, tilt) zeigt.

    roll_grad dreht das Bild um die Blickrichtung (positiv = im Uhrzeigersinn,
    von hinten durch die Kamera gesehen).
    """
    p = math.radians(pan_grad)
    vorn = richtung(pan_grad, tilt_grad)
    rechts = np.array([math.cos(p), 0.0, -math.sin(p)])
    unten = np.cross(vorn, rechts)
    r = math.radians(roll_grad)
    rechts, unten = (math.cos(r) * rechts + math.sin(r) * unten,
                     -math.sin(r) * rechts + math.cos(r) * unten)
    return np.column_stack([rechts, unten, vorn])


def bbox_mitte(bbox: dict) -> tuple[float, float]:
    """Mittelpunkt einer Bounding Box im Event-Format {"x", "y", "w", "h"} (Pixel, x/y = links oben)."""
    return bbox["x"] + bbox["w"] / 2, bbox["y"] + bbox["h"] / 2


def kalibriere_rotation(paare) -> np.ndarray:
    """Schaetzt die Drehung Kamera -> Basis aus Messpaaren (Kabsch-Verfahren).

    paare: Liste von (strahl_kamera, (pan, tilt)), z. B. erzeugt mit
    Kamera.strahl_kamera(u, v) fuer einen Orientierungspunkt und den Pan-/Tilt-
    Winkeln, bei denen die Tracking-Kamera genau auf diesen Punkt zeigt.
    Mindestens 3 Punkte, besser 5-6, gut ueber das Bild verteilt.
    """
    if len(paare) < 3:
        raise ValueError("mindestens 3 Messpaare noetig")
    a = np.array([np.asarray(s, float) / np.linalg.norm(s) for s, _ in paare])
    b = np.array([richtung(p, t) for _, (p, t) in paare])
    u, _, vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    return vt.T @ np.diag([1.0, 1.0, d]) @ u.T


def winkelfehler_je_punkt(r_schaetzung: np.ndarray, paare) -> list[float]:
    """Winkelfehler (Grad) jedes Messpaars: Wie weit liegt die berechnete Richtung daneben?"""
    fehler = []
    for s, (p, t) in paare:
        v = r_schaetzung @ (np.asarray(s, float) / np.linalg.norm(s))
        cos = float(np.clip(v @ richtung(p, t), -1.0, 1.0))
        fehler.append(math.degrees(math.acos(cos)))
    return fehler


def winkelfehler_grad(r_schaetzung: np.ndarray, paare) -> float:
    """Mittlerer Winkelfehler (Grad) einer Drehmatrix auf Messpaaren, zur Kontrolle der Kalibrierung."""
    return float(np.mean(winkelfehler_je_punkt(r_schaetzung, paare)))


# ---------------------------------------------------------------------------
# Kamera
# ---------------------------------------------------------------------------

@dataclass
class Kamera:
    """Eine feste Kamera mit Kalibrierdaten und Lage relativ zur Plattform."""
    breite: int
    hoehe: int
    fx: float
    fy: float
    cx: float
    cy: float
    verzerrung: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)   # OpenCV-Reihenfolge k1, k2, p1, p2, k3
    rotation: np.ndarray = field(default_factory=lambda: np.eye(3))
    # Randverzerrung von Weitwinkel-Webcams als ein Wert (Divisionsmodell nach Fitzgibbon):
    # unverzerrt = verzerrt / (1 + rand * r^2). Negativ = Tonne (typisch fuer Weitwinkel).
    # Wird von kalibriere_kamera geschaetzt; 0 = keine Verzerrung.
    rand: float = 0.0

    @classmethod
    def aus_sichtfeld(cls, breite: int, hoehe: int, hfov_grad: float,
                      vfov_grad: float | None = None, ausrichtung=(0.0, 0.0, 0.0)) -> "Kamera":
        """Ohne Kalibrierung: Brennweite aus dem horizontalen Sichtfeld (Datenblatt).

        ausrichtung = (pan, tilt[, roll]) in Grad: wohin die Bildmitte zeigt.
        """
        fx = (breite / 2) / math.tan(math.radians(hfov_grad) / 2)
        fy = fx if vfov_grad is None else (hoehe / 2) / math.tan(math.radians(vfov_grad) / 2)
        return cls(breite, hoehe, fx, fy, breite / 2, hoehe / 2,
                   rotation=rotation_aus_ausrichtung(*ausrichtung))

    @classmethod
    def aus_opencv(cls, kameramatrix, verzerrung, breite: int, hoehe: int,
                   ausrichtung=(0.0, 0.0, 0.0)) -> "Kamera":
        """Mit Ergebnis von cv2.calibrateCamera (Kameramatrix 3x3, Verzerrungskoeffizienten)."""
        k = np.asarray(kameramatrix, float)
        d = tuple(np.asarray(verzerrung, float).ravel()[:5]) + (0.0,) * max(0, 5 - np.size(verzerrung))
        return cls(breite, hoehe, k[0, 0], k[1, 1], k[0, 2], k[1, 2], d,
                   rotation_aus_ausrichtung(*ausrichtung))

    # -- Geometrie ---------------------------------------------------------

    def _entzerren(self, xd: float, yd: float, schritte: int = 20) -> tuple[float, float]:
        """Normierte verzerrte Koordinaten -> unverzerrt (iterativ, wie cv2.undistortPoints)."""
        k1, k2, p1, p2, k3 = self.verzerrung
        if not any(self.verzerrung):
            return xd, yd
        x, y = xd, yd
        for _ in range(schritte):
            r2 = x * x + y * y
            radial = 1 + k1 * r2 + k2 * r2 ** 2 + k3 * r2 ** 3
            dx = 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
            dy = p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
            x, y = (xd - dx) / radial, (yd - dy) / radial
        return x, y

    def strahl_kamera(self, u: float, v: float) -> np.ndarray:
        """Pixel -> Einheitsvektor im Kamerasystem."""
        x, y = (u - self.cx) / self.fx, (v - self.cy) / self.fy
        if self.rand:
            f = 1.0 / (1.0 + self.rand * (x * x + y * y))
            x, y = x * f, y * f
        x, y = self._entzerren(x, y)
        s = np.array([x, y, 1.0])
        return s / np.linalg.norm(s)

    def pixel_zu_strahl(self, u: float, v: float) -> np.ndarray:
        """Pixel -> Einheitsvektor im Basissystem der Plattform."""
        return self.rotation @ self.strahl_kamera(u, v)

    def pixel_zu_pan_tilt(self, u: float, v: float) -> tuple[float, float]:
        """Pixel -> (pan, tilt) in Grad, auf die die Plattform schwenken muss."""
        return strahl_zu_pan_tilt(self.pixel_zu_strahl(u, v))

    def pan_tilt_zu_pixel(self, pan_grad: float, tilt_grad: float):
        """Umkehrung (ohne OpenCV-Verzerrung): wo im Bild liegt die Richtung (pan, tilt)? None, wenn hinter der Kamera."""
        s = self.rotation.T @ richtung(pan_grad, tilt_grad)
        if s[2] <= 0:
            return None
        x, y = s[0] / s[2], s[1] / s[2]
        if self.rand:
            # r_u = r_d / (1 + rand * r_d^2) nach r_d aufloesen
            ru = math.hypot(x, y)
            d = 1 - 4 * self.rand * ru * ru
            if ru > 1e-12:
                if d < 0:
                    return None                       # ausserhalb dessen, was die Linse abbildet
                rd = (1 - math.sqrt(d)) / (2 * self.rand * ru)
                x, y = x * rd / ru, y * rd / ru
        return self.cx + self.fx * x, self.cy + self.fy * y


# ---------------------------------------------------------------------------
# Mehrere feste Kameras
# ---------------------------------------------------------------------------

class KameraSystem:
    """Alle festen Kameras, adressiert ueber die camera_id aus dem Event.

    Beispiel mit zwei Webcams, die 30 Grad nach links bzw. rechts zeigen:
        system = KameraSystem({
            "cam-1": Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(-30, 15)),
            "cam-2": Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(30, 15)),
        })
        pan, tilt = system.ziel_aus_event(event)
    """

    def __init__(self, kameras: dict):
        if not kameras:
            raise ValueError("mindestens eine Kamera noetig")
        self.kameras = dict(kameras)

    def pan_tilt(self, camera_id: str, u: float, v: float) -> tuple[float, float]:
        if camera_id not in self.kameras:
            raise KeyError(f"unbekannte Kamera {camera_id!r}, bekannt: {sorted(self.kameras)}")
        return self.kameras[camera_id].pixel_zu_pan_tilt(u, v)

    def ziel_aus_event(self, event: dict) -> tuple[float, float]:
        """Ein Erkennungs-Event (camera_id + bbox) -> (pan, tilt)."""
        return self.pan_tilt(event["camera_id"], *bbox_mitte(event["bbox"]))

    def ziel_aus_events(self, events) -> tuple[float, float]:
        """Mehrere gleichzeitige Erkennungen derselben Drohne, z. B. wenn sie im
        Ueberlappungsbereich beider Webcams ist -> eine gemeinsame Richtung.

        Die Richtungen werden nach Konfidenz gewichtet gemittelt. Das ist
        zulaessig, weil alle Kameras dicht beieinander sitzen und die Drohne weit
        weg ist (Fehler etwa Abstand/Entfernung).
        """
        summe = np.zeros(3)
        for e in events:
            kamera = self.kameras[e["camera_id"]]
            summe += e.get("confidence", 1.0) * kamera.pixel_zu_strahl(*bbox_mitte(e["bbox"]))
        if not np.any(summe):
            raise ValueError("keine verwertbaren Erkennungen")
        return strahl_zu_pan_tilt(summe)

    def sieht(self, pan_grad: float, tilt_grad: float) -> list[str]:
        """Welche Kameras haben die Richtung (pan, tilt) im Bild? Hilfreich fuer die Planung der Sichtbereiche."""
        treffer = []
        for cid, k in self.kameras.items():
            px = k.pan_tilt_zu_pixel(pan_grad, tilt_grad)
            if px and 0 <= px[0] < k.breite and 0 <= px[1] < k.hoehe:
                treffer.append(cid)
        return treffer


def kalibriere_kamera(kamera: Kamera, messungen, sichtfeld: bool = True, verzerrung: bool = True) -> dict:
    """Kalibrierung einer festen Kamera aus Messungen (u, v, pan, tilt).

    Schaetzt immer die Drehung (Lage der Kamera). Zusaetzlich, wenn gewuenscht:
      sichtfeld:   die Brennweite, falls das Sichtfeld aus dem Datenblatt nicht stimmt
      verzerrung:  die Randverzerrung (Kamera.rand), Weitwinkel-Webcams verzerren am Rand
    Gesucht wird mit einem immer feineren Raster; die Drehung kommt fuer jeden
    Rasterpunkt aus dem Kabsch-Verfahren. Der Ausgangszustand liegt immer im Raster,
    das Ergebnis ist also nie schlechter als die reine Drehung.

    Rueckgabe: dict mit rotation, fx, fy, rand, fehler (Mittel), fehler_je_punkt,
    fehler_nur_drehung (zum Vergleich) und hfov_grad.
    """
    messungen = [tuple(map(float, m)) for m in messungen]
    if len(messungen) < 3:
        raise ValueError("mindestens 3 Messungen noetig")
    ecke = (kamera.breite / 2 / kamera.fx) ** 2 + (kamera.hoehe / 2 / kamera.fy) ** 2

    def bewerte(lf: float, rand: float):
        faktor = math.exp(lf)
        # Bildecke muss abbildbar bleiben, sonst kippt das Modell am Rand
        if 1 + rand * ecke / faktor ** 2 < 0.25:
            return math.inf, None, None, None
        k = Kamera(kamera.breite, kamera.hoehe, kamera.fx * faktor, kamera.fy * faktor,
                   kamera.cx, kamera.cy, kamera.verzerrung, rand=rand)
        paare = [(k.strahl_kamera(u, v), (p, t)) for u, v, p, t in messungen]
        r = kalibriere_rotation(paare)
        return winkelfehler_grad(r, paare), r, paare, k

    bester = (bewerte(0.0, kamera.rand)[0], 0.0, kamera.rand)      # (fehler, log(faktor), rand)
    fehler_start = bester[0]
    weite_f = 0.4 if sichtfeld else 0.0
    weite_r = 0.3 if verzerrung else 0.0
    for _ in range(6):
        _, lf0, r0 = bester
        for lf in np.linspace(lf0 - weite_f, lf0 + weite_f, 11 if weite_f else 1):
            for rand in np.linspace(r0 - weite_r, r0 + weite_r, 11 if weite_r else 1):
                fehler = bewerte(float(lf), float(rand))[0]
                if fehler < bester[0] - 1e-12:
                    bester = (fehler, float(lf), float(rand))
        weite_f, weite_r = weite_f / 3, weite_r / 3
    fehler, r, paare, k = bewerte(bester[1], bester[2])
    return {
        "rotation": r, "fx": k.fx, "fy": k.fy, "rand": k.rand,
        "fehler": fehler, "fehler_je_punkt": winkelfehler_je_punkt(r, paare),
        "fehler_nur_drehung": fehler_start,
        "hfov_grad": math.degrees(2 * math.atan(kamera.breite / 2 / k.fx)),
    }


# ---------------------------------------------------------------------------
# Plattform: geometrische Winkel -> Servowinkel
# ---------------------------------------------------------------------------

@dataclass
class Achse:
    """Eine Servoachse. mitte = Servowinkel bei geometrisch 0 Grad."""
    mitte: float = 90.0
    richtung: int = 1          # +1 oder -1, je nachdem wie der Servo eingebaut ist
    minimum: float = 0.0
    maximum: float = 180.0

    def zu_servo(self, grad: float) -> float:
        return max(self.minimum, min(self.maximum, self.mitte + self.richtung * grad))

    def von_servo(self, servo_grad: float) -> float:
        return (servo_grad - self.mitte) * self.richtung


@dataclass
class Plattform:
    pan: Achse = field(default_factory=Achse)
    tilt: Achse = field(default_factory=Achse)

    def servo_winkel(self, pan_grad: float, tilt_grad: float) -> tuple[float, float]:
        return self.pan.zu_servo(pan_grad), self.tilt.zu_servo(tilt_grad)

    def move_befehl(self, pan_grad: float, tilt_grad: float) -> str:
        """Befehl im Protokoll der Pico-Firmware (main.py)."""
        sp, st = self.servo_winkel(pan_grad, tilt_grad)
        return f"MOVE {sp:.1f} {st:.1f}"

    def begrenzen(self, pan_grad: float, tilt_grad: float) -> tuple[float, float]:
        """Naechste erreichbare Richtung: jede Achse bis zu ihrem Anschlag."""
        sp, st = self.servo_winkel(pan_grad, tilt_grad)       # zu_servo begrenzt schon
        return self.pan.von_servo(sp), self.tilt.von_servo(st)

    def erreichbar(self, pan_grad: float, tilt_grad: float) -> bool:
        """False, wenn mindestens eine Achse am Anschlag begrenzt wuerde."""
        for achse, grad in ((self.pan, pan_grad), (self.tilt, tilt_grad)):
            roh = achse.mitte + achse.richtung * grad
            if not achse.minimum <= roh <= achse.maximum:
                return False
        return True


# ---------------------------------------------------------------------------
# Stufe 2: Korrektur aus dem Bild der Tracking-Kamera
# ---------------------------------------------------------------------------

def korrektur_aus_tracking_bild(u: float, v: float, tracking: Kamera) -> tuple[float, float]:
    """Pixel des Ziels im Bild der Tracking-Kamera -> noetige Aenderung (d_pan, d_tilt) in Grad.

    Die Tracking-Kamera sitzt auf der Plattform, ihre rotation bleibt deshalb die
    Einheitsmatrix. Das Ergebnis ist der Fehler fuer den Regler in Stufe 2.
    """
    return strahl_zu_pan_tilt(tracking.strahl_kamera(u, v))


# ---------------------------------------------------------------------------
# Kommandozeile zum Ausprobieren
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Pixel einer festen Kamera -> Pan/Tilt -> MOVE-Befehl")
    ap.add_argument("u", type=float, help="Pixel x")
    ap.add_argument("v", type=float, help="Pixel y")
    ap.add_argument("--breite", type=int, default=1920)
    ap.add_argument("--hoehe", type=int, default=1080)
    ap.add_argument("--hfov", type=float, default=60.0, help="horizontales Sichtfeld in Grad")
    ap.add_argument("--pan", type=float, default=0.0, help="wohin die Kamera zeigt: pan in Grad")
    ap.add_argument("--tilt", type=float, default=0.0, help="wohin die Kamera zeigt: tilt in Grad")
    a = ap.parse_args()

    kamera = Kamera.aus_sichtfeld(a.breite, a.hoehe, a.hfov, ausrichtung=(a.pan, a.tilt))
    pan, tilt = kamera.pixel_zu_pan_tilt(a.u, a.v)
    plattform = Plattform()
    print(f"pan {pan:+.2f} Grad, tilt {tilt:+.2f} Grad")
    print(plattform.move_befehl(pan, tilt) + ("" if plattform.erreichbar(pan, tilt) else "   (am Anschlag begrenzt)"))


if __name__ == "__main__":
    main()

