#!/usr/bin/env python3
"""Pan-Tilt-Steuerung am Pi 5: Tastatur + Winkelberechnung (winkel.py).

Tasten:
  Pfeiltasten   Plattform bewegen (in Grad, 0/0 = geradeaus und waagerecht)
  + / -         Schrittweite verdoppeln / halbieren
  h             zurueck auf 0/0
  z             Ziel anfahren: Kamera und Pixel eingeben, z. B. "cam-2 1500 300"
  k             Kalibrierpunkt speichern: Tracking-Kamera zeigt gerade auf einen
                Punkt, dazu Kamera und Pixel dieses Punkts im Webcam-Bild eingeben
  c             Kalibrierung berechnen (ab 3 Punkten je Webcam) und speichern
  q             beenden

Start:   python3 pantilt_steuerung.py [/dev/ttyACM0]
Vorher:  sudo apt install python3-serial python3-numpy
         winkel.py im selben Ordner, Thonny geschlossen.
"""
import curses
import json
import sys
from pathlib import Path

import numpy as np

from winkel import Achse, Kamera, KameraSystem, Plattform, kalibriere_rotation, winkelfehler_grad

# ---------------------------------------------------------------------------
# Konfiguration: hier eure Werte eintragen
# ---------------------------------------------------------------------------

# Feste Webcams: Aufloesung, horizontales Sichtfeld und grobe Ausrichtung (pan, tilt)
# von der Plattform aus gesehen. Die Ausrichtung wird durch die Kalibrierung ersetzt.
KAMERAS = {
    "cam-1": Kamera.aus_sichtfeld(1920, 1080, hfov_grad=60, ausrichtung=(-30, 25)),
    "cam-2": Kamera.aus_sichtfeld(1920, 1080, hfov_grad=60, ausrichtung=(30, 25)),
}

# Servo-Winkel bei 0/0 und Drehrichtung; Grenzen wie in main.py auf dem Pico
PLATTFORM = Plattform(
    pan=Achse(mitte=90, richtung=1, minimum=0, maximum=180),
    tilt=Achse(mitte=90, richtung=1, minimum=0, maximum=180),
)

KALIBRIER_DATEI = Path(__file__).with_name("kalibrierung.json")


# ---------------------------------------------------------------------------
# Logik (ohne Bildschirm, damit sie sich testen laesst)
# ---------------------------------------------------------------------------

class Steuerung:
    def __init__(self, ser, kameras=KAMERAS, plattform=PLATTFORM, kalibrier_datei=KALIBRIER_DATEI):
        self.ser = ser
        self.system = KameraSystem(kameras)
        self.plattform = plattform
        self.datei = Path(kalibrier_datei)
        self.pan = 0.0
        self.tilt = 0.0
        self.punkte = {cid: [] for cid in kameras}       # Kalibrierpunkte je Webcam
        self.meldung = self.laden()

    def senden(self, befehl: str) -> str:
        self.ser.reset_input_buffer()
        self.ser.write((befehl + "\n").encode())
        return self.ser.readline().decode(errors="replace").strip() or "(keine Antwort)"

    def fahren(self, pan: float, tilt: float) -> str:
        if not self.plattform.erreichbar(pan, tilt):
            return f"nicht erreichbar: pan {pan:+.1f}, tilt {tilt:+.1f} (ausserhalb der Servogrenzen)"
        self.pan, self.tilt = pan, tilt
        return self.senden(self.plattform.move_befehl(pan, tilt))

    def schritt(self, d_pan: float, d_tilt: float) -> str:
        return self.fahren(self.pan + d_pan, self.tilt + d_tilt)

    def ziel(self, eingabe: str) -> str:
        cid, u, v = self._kamera_pixel(eingabe)
        pan, tilt = self.system.pan_tilt(cid, u, v)
        antwort = self.fahren(pan, tilt)
        return f"{cid} ({u:.0f}, {v:.0f}) -> pan {pan:+.2f}, tilt {tilt:+.2f}: {antwort}"

    def kalibrierpunkt(self, eingabe: str) -> str:
        cid, u, v = self._kamera_pixel(eingabe)
        strahl = self.system.kameras[cid].strahl_kamera(u, v)
        self.punkte[cid].append((strahl, (self.pan, self.tilt)))
        return f"Punkt {len(self.punkte[cid])} fuer {cid} gespeichert (pan {self.pan:+.1f}, tilt {self.tilt:+.1f})"

    def kalibrieren(self) -> str:
        ergebnisse, daten = [], self._datei_lesen()
        for cid, paare in self.punkte.items():
            if len(paare) < 3:
                ergebnisse.append(f"{cid}: {len(paare)}/3 Punkte")
                continue
            r = kalibriere_rotation(paare)
            self.system.kameras[cid].rotation = r
            daten[cid] = r.tolist()
            ergebnisse.append(f"{cid}: Fehler {winkelfehler_grad(r, paare):.2f} Grad bei {len(paare)} Punkten")
        self.datei.write_text(json.dumps(daten, indent=2))
        return " | ".join(ergebnisse) + f"  -> gespeichert in {self.datei.name}"

    def laden(self) -> str:
        daten = self._datei_lesen()
        geladen = [cid for cid in daten if cid in self.system.kameras]
        for cid in geladen:
            self.system.kameras[cid].rotation = np.array(daten[cid], dtype=float)
        return f"Kalibrierung geladen: {', '.join(geladen)}" if geladen else "noch keine Kalibrierung"

    def _datei_lesen(self) -> dict:
        try:
            return json.loads(self.datei.read_text())
        except (OSError, ValueError):
            return {}

    def _kamera_pixel(self, eingabe: str):
        teile = eingabe.split()
        if len(teile) != 3:
            raise ValueError('Format: "<kamera> <u> <v>", z. B. "cam-1 960 540"')
        if teile[0] not in self.system.kameras:
            raise ValueError(f"unbekannte Kamera {teile[0]}, bekannt: {', '.join(self.system.kameras)}")
        return teile[0], float(teile[1]), float(teile[2])


# ---------------------------------------------------------------------------
# Bildschirm
# ---------------------------------------------------------------------------

def zeile(scr, y: int, text: str):
    """Text ausgeben, auf Fensterbreite gekuerzt (schmale Terminals)."""
    hoehe, breite = scr.getmaxyx()
    if y < hoehe:
        try:
            scr.addstr(y, 0, text[:breite - 1])
        except curses.error:
            pass


def eingabe_lesen(scr, zeile_nr: int, frage: str) -> str:
    curses.echo()
    curses.curs_set(1)
    scr.timeout(-1)
    scr.move(zeile_nr, 0)
    scr.clrtoeol()
    zeile(scr, zeile_nr, frage)
    text = scr.getstr(zeile_nr, min(len(frage), scr.getmaxyx()[1] - 2), 40).decode(errors="replace")
    curses.noecho()
    curses.curs_set(0)
    scr.timeout(200)
    return text


def oberflaeche(scr, st: Steuerung):
    curses.curs_set(0)
    scr.timeout(200)
    schritt = 2.0
    st.meldung = st.fahren(0, 0) + " | " + st.meldung
    while True:
        scr.erase()
        zeile(scr, 0, "Pan-Tilt-Steuerung")
        zeile(scr, 1, "Pfeile: bewegen  +/-: Schritt  h: Mitte  q: Ende")
        zeile(scr, 2, "z: Ziel anfahren  k: Kalibrierpunkt  c: kalibrieren")
        zeile(scr, 4, f"Plattform: pan {st.pan:+6.1f}  tilt {st.tilt:+6.1f}  Grad   Schritt {schritt:.1f}")
        sp, stt = st.plattform.servo_winkel(st.pan, st.tilt)
        zeile(scr, 5, f"Servos:    {sp:6.1f}  {stt:6.1f}   Pico: {st.senden('POS?')}")
        punkte = "  ".join(f"{cid}: {len(p)}" for cid, p in st.punkte.items())
        zeile(scr, 6, f"Kalibrierpunkte: {punkte}")
        zeile(scr, 8, st.meldung)
        scr.refresh()

        taste = scr.getch()
        try:
            if taste in (ord("q"), ord("Q")):
                break
            elif taste == curses.KEY_LEFT:
                st.meldung = st.schritt(-schritt, 0)
            elif taste == curses.KEY_RIGHT:
                st.meldung = st.schritt(schritt, 0)
            elif taste == curses.KEY_UP:
                st.meldung = st.schritt(0, schritt)
            elif taste == curses.KEY_DOWN:
                st.meldung = st.schritt(0, -schritt)
            elif taste in (ord("+"), ord("=")):
                schritt = min(20.0, schritt * 2)
            elif taste == ord("-"):
                schritt = max(0.25, schritt / 2)
            elif taste == ord("h"):
                st.meldung = st.fahren(0, 0)
            elif taste == ord("z"):
                st.meldung = st.ziel(eingabe_lesen(scr, 10, "Ziel (kamera u v): "))
            elif taste == ord("k"):
                st.meldung = st.kalibrierpunkt(eingabe_lesen(scr, 10, "Punkt im Webcam-Bild (kamera u v): "))
            elif taste == ord("c"):
                st.meldung = st.kalibrieren()
        except (ValueError, KeyError) as fehler:
            st.meldung = f"Fehler: {fehler}"


def main():
    import serial
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    with serial.Serial(port, 115200, timeout=0.3) as ser:
        curses.wrapper(oberflaeche, Steuerung(ser))


if __name__ == "__main__":
    main()
