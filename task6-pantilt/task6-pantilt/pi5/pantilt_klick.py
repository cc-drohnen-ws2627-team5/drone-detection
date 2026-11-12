#!/usr/bin/env python3
"""Klick-Steuerung: Webcam-Bild anzeigen, hineinklicken, die Plattform schwenkt hin.

Jede Webcam bekommt ein eigenes Fenster. Ein roter Kreis zeigt, wohin die
Plattform gerade zeigt (berechnet mit winkel.py), ein gruenes Kreuz den letzten Klick.

Maus und Tasten (in einem der Bildfenster):
  Linksklick    ZIELEN: Plattform faehrt auf den Punkt
                KALIBRIEREN: Klick = Kalibrierpunkt (Plattform bleibt stehen)
  m             Modus wechseln: ZIELEN <-> KALIBRIEREN
  w a s d       Plattform von Hand bewegen (hoch, links, runter, rechts)
  + / -         Schrittweite verdoppeln / halbieren
  h             zurueck auf 0/0
  c             Kalibrierung berechnen und speichern (ab 3 Punkten je Webcam)
  q / Esc       beenden

Kalibrieren:
  1. Modus KALIBRIEREN (m).
  2. Mit w a s d die HQ Camera genau auf einen markanten Punkt richten
     (Fadenkreuz im HQ-Fenster).
  3. Den gleichen Punkt im Webcam-Fenster anklicken.
  4. Mit 4-6 Punkten je Webcam wiederholen, dann c.

Start:   python3 pantilt_klick.py [--pico /dev/ttyACM0] [--ohne-hq]
Vorher:  sudo apt install python3-opencv python3-serial python3-numpy python3-picamera2
         winkel.py und pantilt_steuerung.py im selben Ordner.
         Webcam-Geraete finden: v4l2-ctl --list-devices
"""
import argparse

import cv2

from pantilt_steuerung import KAMERAS, PLATTFORM, Steuerung

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Welches Video-Geraet ist welche Webcam? Namen wie in KAMERAS (pantilt_steuerung.py).
# Am Pi 5 belegen die Kamera-Schnittstellen /dev/video0..., die USB-Webcams haben
# oft hoehere Nummern. Pruefen mit: v4l2-ctl --list-devices
WEBCAM_GERAETE = {
    "cam-1": "/dev/video0",
    "cam-2": "/dev/video2",
}

ANZEIGE_BREITE = 960        # Fensterbreite in Pixeln; das Kamerabild wird dafuer verkleinert
ROT, GRUEN, WEISS, SCHWARZ = (0, 0, 255), (0, 255, 0), (255, 255, 255), (0, 0, 0)


# ---------------------------------------------------------------------------
# Logik (ohne Fenster, damit sie sich testen laesst)
# ---------------------------------------------------------------------------

def fenster_zu_kamerapixel(x, y, bild_groesse, anzeige_groesse, kamera):
    """Klick im (verkleinerten) Fenster -> Pixel im Koordinatensystem der Kamera aus KAMERAS.

    Liefert die Webcam ein Bild in anderer Aufloesung als in KAMERAS eingetragen,
    wird ebenfalls umgerechnet.
    """
    bw, bh = bild_groesse
    aw, ah = anzeige_groesse
    u_bild, v_bild = x * bw / aw, y * bh / ah
    return u_bild * kamera.breite / bw, v_bild * kamera.hoehe / bh


def kamerapixel_zu_fenster(u, v, anzeige_groesse, kamera):
    aw, ah = anzeige_groesse
    return int(round(u * aw / kamera.breite)), int(round(v * ah / kamera.hoehe))


class KlickSteuerung:
    def __init__(self, steuerung: Steuerung):
        self.st = steuerung
        self.modus = "ZIELEN"
        self.schritt = 2.0
        self.letzter_klick = {}               # cid -> (u, v) in Kamerapixeln

    def klick(self, cid: str, u: float, v: float) -> str:
        self.letzter_klick[cid] = (u, v)
        eingabe = f"{cid} {u:.1f} {v:.1f}"
        try:
            if self.modus == "ZIELEN":
                self.st.meldung = self.st.ziel(eingabe)
            else:
                self.st.meldung = self.st.kalibrierpunkt(eingabe)
        except (ValueError, KeyError) as fehler:
            self.st.meldung = f"Fehler: {fehler}"
        return self.st.meldung

    def taste(self, zeichen: str) -> bool:
        """Verarbeitet eine Taste. False = Programm beenden."""
        st = self.st
        bewegung = {"w": (0, 1), "s": (0, -1), "a": (-1, 0), "d": (1, 0)}
        if zeichen in ("q", "\x1b"):
            return False
        if zeichen in bewegung:
            dp, dt = bewegung[zeichen]
            st.meldung = st.schritt(dp * self.schritt, dt * self.schritt)
        elif zeichen in ("+", "="):
            self.schritt = min(20.0, self.schritt * 2)
        elif zeichen == "-":
            self.schritt = max(0.25, self.schritt / 2)
        elif zeichen == "h":
            st.meldung = st.fahren(0, 0)
        elif zeichen == "m":
            self.modus = "KALIBRIEREN" if self.modus == "ZIELEN" else "ZIELEN"
            st.meldung = f"Modus: {self.modus}"
        elif zeichen == "c":
            st.meldung = st.kalibrieren()
        return True

    def overlay(self, bild, cid: str):
        """Zeichnet Plattformrichtung, letzten Klick und Status in das (verkleinerte) Bild."""
        kamera = self.st.system.kameras[cid]
        groesse = (bild.shape[1], bild.shape[0])
        ziel = kamera.pan_tilt_zu_pixel(self.st.pan, self.st.tilt)
        if ziel:
            p = kamerapixel_zu_fenster(*ziel, groesse, kamera)
            if 0 <= p[0] < groesse[0] and 0 <= p[1] < groesse[1]:
                cv2.circle(bild, p, 14, ROT, 2)
                cv2.circle(bild, p, 2, ROT, -1)
        if cid in self.letzter_klick:
            p = kamerapixel_zu_fenster(*self.letzter_klick[cid], groesse, kamera)
            cv2.drawMarker(bild, p, GRUEN, cv2.MARKER_CROSS, 22, 2)
        punkte = len(self.st.punkte.get(cid, []))
        zeilen = [
            f"{cid}  Modus: {self.modus}  (m wechselt)",
            f"Plattform pan {self.st.pan:+.1f}  tilt {self.st.tilt:+.1f}  Schritt {self.schritt:g}  Kalibrierpunkte: {punkte}",
            self.st.meldung[:110],
        ]
        # dunkler Balken hinter dem Text, damit er auf hellem Himmel lesbar bleibt
        cv2.rectangle(bild, (0, 0), (bild.shape[1], 8 + 22 * len(zeilen)), SCHWARZ, -1)
        for i, text in enumerate(zeilen):
            cv2.putText(bild, text, (8, 22 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WEISS, 1, cv2.LINE_AA)
        return bild


def fadenkreuz(bild):
    h, w = bild.shape[:2]
    cv2.line(bild, (w // 2 - 30, h // 2), (w // 2 + 30, h // 2), ROT, 1)
    cv2.line(bild, (w // 2, h // 2 - 30), (w // 2, h // 2 + 30), ROT, 1)
    cv2.circle(bild, (w // 2, h // 2), 12, ROT, 1)
    return bild


# ---------------------------------------------------------------------------
# Kameras und Fenster
# ---------------------------------------------------------------------------

def webcam_oeffnen(geraet: str, kamera):
    cap = cv2.VideoCapture(geraet, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"Webcam {geraet} laesst sich nicht oeffnen (v4l2-ctl --list-devices)")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # sonst schafft USB kein Full HD
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, kamera.breite)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, kamera.hoehe)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def hq_oeffnen():
    try:
        from picamera2 import Picamera2
    except ImportError:
        print("picamera2 nicht installiert, HQ-Fenster aus (sudo apt install python3-picamera2)")
        return None
    hq = Picamera2()
    hq.configure(hq.create_preview_configuration(main={"size": (1014, 760), "format": "RGB888"}))
    hq.start()
    return hq


def main():
    import serial
    ap = argparse.ArgumentParser(description="Webcam anklicken -> Pan-Tilt schwenkt hin")
    ap.add_argument("--pico", default="/dev/ttyACM0")
    ap.add_argument("--ohne-hq", action="store_true", help="kein Fenster fuer die HQ Camera")
    args = ap.parse_args()

    webcams = {cid: webcam_oeffnen(g, KAMERAS[cid]) for cid, g in WEBCAM_GERAETE.items()}
    hq = None if args.ohne_hq else hq_oeffnen()

    with serial.Serial(args.pico, 115200, timeout=0.3) as ser:
        app = KlickSteuerung(Steuerung(ser, KAMERAS, PLATTFORM))
        app.st.meldung = app.st.fahren(0, 0) + " | " + app.st.meldung
        bildgroesse = {}                          # cid -> (Breite, Hoehe) des Originalbilds

        def maus(ereignis, x, y, flags, cid):
            if ereignis == cv2.EVENT_LBUTTONDOWN and cid in bildgroesse:
                bw, bh = bildgroesse[cid]
                anzeige = (ANZEIGE_BREITE, round(ANZEIGE_BREITE * bh / bw))
                app.klick(cid, *fenster_zu_kamerapixel(x, y, (bw, bh), anzeige, KAMERAS[cid]))

        for cid in webcams:
            cv2.namedWindow(cid, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(cid, maus, cid)

        try:
            while True:
                for cid, cap in webcams.items():
                    ok, bild = cap.read()
                    if not ok:
                        continue
                    bildgroesse[cid] = (bild.shape[1], bild.shape[0])
                    hoehe = round(ANZEIGE_BREITE * bild.shape[0] / bild.shape[1])
                    klein = cv2.resize(bild, (ANZEIGE_BREITE, hoehe))
                    cv2.imshow(cid, app.overlay(klein, cid))
                if hq is not None:
                    cv2.imshow("HQ Camera", fadenkreuz(hq.capture_array()))
                taste = cv2.waitKey(1) & 0xFF
                if taste != 255 and not app.taste(chr(taste)):
                    break
        finally:
            for cap in webcams.values():
                cap.release()
            if hq is not None:
                hq.stop()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
