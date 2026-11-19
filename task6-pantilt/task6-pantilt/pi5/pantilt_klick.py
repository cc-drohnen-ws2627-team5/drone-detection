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
  x             letzten Kalibrierpunkt loeschen (falsch geklickt)
  c             Kalibrierung berechnen und speichern (ab 3 Punkten je Webcam,
                ab 6 Punkten wird auch die Randverzerrung der Webcam berechnet)
  q / Esc       beenden

Kalibrieren:
  1. Modus KALIBRIEREN (m).
  2. Mit w a s d die HQ Camera genau auf einen markanten Punkt richten
     (Fadenkreuz im HQ-Fenster).
  3. Den gleichen Punkt im Webcam-Fenster anklicken.
  4. Mit 4-6 Punkten je Webcam wiederholen, dann c.

Start:   python3 pantilt_klick.py [--ohne-hq] [--pico anschluss]
         Der Pico wird von selbst gefunden. Am Laptop immer mit --ohne-hq starten,
         die HQ Camera laeuft nur am Pi.
Vorher:  Pi:      sudo apt install python3-opencv python3-serial python3-numpy python3-picamera2
         Laptop:  pip install opencv-python pyserial numpy
         winkel.py und pantilt_steuerung.py im selben Ordner.
"""
import argparse
import sys

import cv2

from pantilt_steuerung import KAMERAS, PLATTFORM, Steuerung, pico_anschluss

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Welches Video-Geraet ist welche Webcam? Namen wie in KAMERAS (pantilt_steuerung.py).
#   Laptop (Mac, Windows): Nummern. 0 ist meist die eingebaute Kamera, die USB-Webcams
#                          sind dann 1 und 2. Zeigt ein Fenster das falsche Bild: tauschen.
#   Pi 5:                  Pfade wie "/dev/video0". Pruefen mit: v4l2-ctl --list-devices
#   Nur eine Webcam angeschlossen (z.B. Laptop mit 2 USB-Anschluessen): die andere Zeile
#   mit # auskommentieren. Jede Webcam laesst sich einzeln kalibrieren, die Ergebnisse
#   bleiben in kalibrierung.json erhalten.
WEBCAM_GERAETE = {
    "cam-1": 1,
    # "cam-2": 2,
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
        self.letzte_kamera = None

    def klick(self, cid: str, u: float, v: float) -> str:
        self.letzter_klick[cid] = (u, v)
        self.letzte_kamera = cid
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
        elif zeichen == "x" and self.letzte_kamera:
            st.meldung = st.punkt_loeschen(self.letzte_kamera)
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
            self.st.meldung[110:220],
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

def webcam_oeffnen(geraet, kamera):
    """geraet: Nummer (0, 1, 2 ...) oder unter Linux ein Pfad wie /dev/video0."""
    if sys.platform.startswith("linux"):
        cap = cv2.VideoCapture(geraet, cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(geraet)
    if not cap.isOpened():
        raise RuntimeError(f"Webcam {geraet} laesst sich nicht oeffnen. Nummer in WEBCAM_GERAETE pruefen.")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # sonst schafft USB kein Full HD
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, kamera.breite)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, kamera.hoehe)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    b, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam {geraet}: liefert {b} x {h}")
    if b and h and abs(b / h - kamera.breite / kamera.hoehe) > 0.02:
        print(f"  ACHTUNG: anderes Seitenverhaeltnis als in KAMERAS ({kamera.breite} x {kamera.hoehe}),"
              f" dort {b} x {h} eintragen")
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
    ap.add_argument("--pico", default=None, help="serieller Anschluss, sonst automatisch")
    ap.add_argument("--ohne-hq", action="store_true", help="kein Fenster fuer die HQ Camera")
    args = ap.parse_args()

    webcams = {cid: webcam_oeffnen(g, KAMERAS[cid]) for cid, g in WEBCAM_GERAETE.items()}
    hq = None if args.ohne_hq else hq_oeffnen()

    with serial.Serial(pico_anschluss(args.pico), 115200, timeout=0.3) as ser:
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
