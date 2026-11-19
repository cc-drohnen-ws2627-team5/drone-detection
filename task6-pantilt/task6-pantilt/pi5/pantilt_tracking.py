#!/usr/bin/env python3
"""Automatisches Nachfuehren: Erkennungen der festen Kameras -> Pan-Tilt-Plattform.

Das ist Stufe 1 von Task 6 ohne Klick: Jede Erkennung (Event) wird mit winkel.py in
Pan/Tilt umgerechnet, und die Plattform faehrt dorthin. Die Kalibrierung aus
pantilt_klick.py (kalibrierung.json) wird automatisch geladen.

Quellen fuer Erkennungen, eine davon waehlen:
  --mqtt HOST     echte Erkennungen vom Broker, Topic sensors/+/detections
  --bewegung      Demo ohne Drohnenerkennung: alles, was sich im Webcam-Bild
                  bewegt, wird verfolgt (Webcams wie in pantilt_klick.py)
  --stdin         Events als JSON-Zeilen von der Tastatur oder aus einer Datei (Test)

Event-Format (wie im Backend, Task 3):
  {"camera_id": "cam-1", "class": "drone", "confidence": 0.87,
   "bbox": {"x": 812, "y": 240, "w": 64, "h": 40}, "track_id": 7}
  bbox in Pixeln der Webcam (Aufloesung wie in KAMERAS), x/y = Ecke links oben.
  track_id ist freiwillig; wenn vorhanden, bleibt die Plattform bei derselben Drohne.

Start:   python3 pantilt_tracking.py --bewegung            (Laptop: zusaetzlich nichts)
         python3 pantilt_tracking.py --mqtt localhost
Vorher:  wie pantilt_klick.py; fuer --mqtt zusaetzlich
         Pi: sudo apt install python3-paho-mqtt   Laptop: pip install paho-mqtt
Beenden: q im Bildfenster (--bewegung) oder Strg+C
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time

from pantilt_steuerung import KAMERAS, PLATTFORM, Steuerung, pico_anschluss


# ---------------------------------------------------------------------------
# Logik (ohne Hardware, damit sie sich testen laesst)
# ---------------------------------------------------------------------------

class Nachfuehrung:
    """Entscheidet, welcher Erkennung die Plattform folgt und wann ein Befehl rausgeht.

    - Erkennungen unter min_konfidenz oder mit falscher Klasse werden ignoriert.
    - Hat die verfolgte Drohne eine track_id, bleibt die Plattform bei ihr, bis sie
      wechsel_nach_s lang nicht mehr gemeldet wurde.
    - Hoechstens alle takt_s ein MOVE und nur bei mehr als totzone_grad Aenderung,
      damit die Servos nicht staendig nachzucken.
    - Ziele ausserhalb des Bereichs werden bis zum Anschlag angefahren.
    - Nach heim_nach_s ohne Erkennung faehrt die Plattform in die Grundstellung.
    """

    def __init__(self, steuerung: Steuerung, klassen=None, min_konfidenz=0.4, takt_s=0.1,
                 totzone_grad=0.5, wechsel_nach_s=1.0, heim_nach_s=10.0, heim=(0.0, 30.0),
                 uhr=time.monotonic):
        self.st = steuerung
        self.klassen = set(klassen) if klassen else None
        self.min_konfidenz = min_konfidenz
        self.takt_s = takt_s
        self.totzone_grad = totzone_grad
        self.wechsel_nach_s = wechsel_nach_s
        self.heim_nach_s = heim_nach_s
        self.heim = heim
        self.uhr = uhr
        self.ziel = None                  # (pan, tilt), wohin die Plattform soll
        self.track = None                 # track_id der verfolgten Drohne
        self.zuletzt_gesehen = None
        self.letzter_befehl = -1e9
        self.gesendet = None              # zuletzt geschickte Richtung
        self.daheim = False

    def event(self, e: dict) -> str | None:
        """Eine Erkennung verarbeiten. Rueckgabe: Grund, falls ignoriert, sonst None."""
        try:
            cid, bbox = e["camera_id"], e["bbox"]
            konfidenz = float(e.get("confidence", 1.0))
        except (KeyError, TypeError, ValueError):
            return "unvollstaendiges Event"
        if cid not in self.st.system.kameras:
            return f"unbekannte Kamera {cid}"
        if konfidenz < self.min_konfidenz:
            return "Konfidenz zu klein"
        if self.klassen and e.get("class") not in self.klassen:
            return f"Klasse {e.get('class')} wird nicht verfolgt"
        jetzt = self.uhr()
        track = e.get("track_id")
        beschaeftigt = (self.track is not None and track is not None and track != self.track
                        and jetzt - self.zuletzt_gesehen < self.wechsel_nach_s)
        if beschaeftigt:
            return f"folge gerade Track {self.track}"
        try:
            pan, tilt = self.st.system.ziel_aus_event(e)
        except (KeyError, TypeError, ValueError):
            return "bbox nicht lesbar"
        self.ziel = self.st.plattform.begrenzen(pan, tilt)
        self.track = track
        self.zuletzt_gesehen = jetzt
        self.daheim = False
        return None

    def takt(self) -> str | None:
        """Regelmaessig aufrufen. Schickt bei Bedarf einen Befehl, Rueckgabe: Meldung oder None."""
        jetzt = self.uhr()
        if self.zuletzt_gesehen is not None and not self.daheim and jetzt - self.zuletzt_gesehen > self.heim_nach_s:
            self.daheim, self.ziel, self.track = True, None, None
            self.gesendet = self.heim
            return "nichts mehr gesehen -> Grundstellung: " + self.st.fahren(*self.heim)
        if self.ziel is None or jetzt - self.letzter_befehl < self.takt_s:
            return None
        if self.gesendet and max(abs(a - b) for a, b in zip(self.ziel, self.gesendet)) < self.totzone_grad:
            return None
        self.letzter_befehl = jetzt
        self.gesendet = self.ziel
        antwort = self.st.fahren(*self.ziel)
        return f"pan {self.ziel[0]:+6.1f}  tilt {self.ziel[1]:+6.1f}  track {self.track}  -> {antwort}"


class BewegungsMelder:
    """Demo-Erkennung: groesste bewegte Flaeche im Webcam-Bild -> Event wie von der Drohnenerkennung."""

    def __init__(self, cid: str, kamera, min_anteil=0.0005, max_anteil=0.3, anlauf_bilder=30):
        import cv2
        self.cv2 = cv2
        self.cid, self.kamera = cid, kamera
        self.hintergrund = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=40, detectShadows=False)
        self.min_anteil, self.max_anteil = min_anteil, max_anteil
        self.anlauf = anlauf_bilder

    def bild(self, bild) -> dict | None:
        cv2 = self.cv2
        h, w = bild.shape[:2]
        klein = cv2.resize(bild, (320, round(320 * h / w)))
        maske = self.hintergrund.apply(klein)
        if self.anlauf > 0:                       # erst den Hintergrund lernen
            self.anlauf -= 1
            return None
        maske = cv2.morphologyEx(maske, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        maske = cv2.dilate(maske, None, iterations=2)
        konturen, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not konturen:
            return None
        groesste = max(konturen, key=cv2.contourArea)
        anteil = cv2.contourArea(groesste) / (klein.shape[0] * klein.shape[1])
        if not self.min_anteil <= anteil <= self.max_anteil:    # Rauschen oder Belichtungssprung
            return None
        x, y, bw, bh = cv2.boundingRect(groesste)
        sx, sy = self.kamera.breite / klein.shape[1], self.kamera.hoehe / klein.shape[0]
        return {"camera_id": self.cid, "class": "bewegung", "confidence": 1.0,
                "bbox": {"x": x * sx, "y": y * sy, "w": bw * sx, "h": bh * sy}}


# ---------------------------------------------------------------------------
# Quellen und Hauptschleife
# ---------------------------------------------------------------------------

def mqtt_starten(host: str, port: int, topic: str, ziel: queue.Queue):
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)     # paho-mqtt 2.x
    except AttributeError:
        client = mqtt.Client()                                      # paho-mqtt 1.x

    def verbunden(c, *args):
        c.subscribe(topic)
        print(f"MQTT verbunden mit {host}:{port}, warte auf {topic}")

    def nachricht(c, userdata, msg):
        try:
            daten = json.loads(msg.payload)
        except ValueError:
            print("kein JSON auf", msg.topic)
            return
        for e in daten if isinstance(daten, list) else [daten]:
            ziel.put(e)

    client.on_connect, client.on_message = verbunden, nachricht
    client.connect(host, port)
    client.loop_start()
    return client


def stdin_starten(ziel: queue.Queue):
    def lesen():
        for zeile in sys.stdin:
            zeile = zeile.strip()
            if zeile:
                try:
                    ziel.put(json.loads(zeile))
                except ValueError:
                    print("kein JSON:", zeile)
    threading.Thread(target=lesen, daemon=True).start()


def main():
    import serial
    ap = argparse.ArgumentParser(description="Erkennungen -> Pan-Tilt nachfuehren")
    quelle = ap.add_mutually_exclusive_group(required=True)
    quelle.add_argument("--mqtt", metavar="HOST", help="Broker, z. B. localhost")
    quelle.add_argument("--bewegung", action="store_true", help="Demo: Bewegung im Webcam-Bild verfolgen")
    quelle.add_argument("--stdin", action="store_true", help="Events als JSON-Zeilen von der Standardeingabe")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="sensors/+/detections")
    ap.add_argument("--klasse", action="append", help="nur diese Klasse verfolgen, z. B. --klasse drone")
    ap.add_argument("--min-konfidenz", type=float, default=0.4)
    ap.add_argument("--pico", default=None, help="serieller Anschluss, sonst automatisch")
    args = ap.parse_args()

    events = queue.Queue()
    webcams, melder = {}, {}
    if args.mqtt:
        mqtt_starten(args.mqtt, args.port, args.topic, events)
    elif args.stdin:
        stdin_starten(events)
    else:
        import cv2
        from pantilt_klick import WEBCAM_GERAETE, webcam_oeffnen
        for cid, geraet in WEBCAM_GERAETE.items():
            webcams[cid] = webcam_oeffnen(geraet, KAMERAS[cid])
            melder[cid] = BewegungsMelder(cid, KAMERAS[cid])
        print("Bewegungs-Demo: die ersten Sekunden ruhig halten, dann bewegt sich etwas vor der Webcam.")

    with serial.Serial(pico_anschluss(args.pico), 115200, timeout=0.3) as ser:
        st = Steuerung(ser, KAMERAS, PLATTFORM)
        print(st.meldung)
        nf = Nachfuehrung(st, klassen=args.klasse, min_konfidenz=args.min_konfidenz)
        print("Grundstellung:", st.fahren(*nf.heim))
        try:
            while True:
                for cid, cap in webcams.items():
                    ok, bild = cap.read()
                    if not ok:
                        continue
                    e = melder[cid].bild(bild)
                    if e:
                        events.put(e)
                        b = e["bbox"]
                        k = KAMERAS[cid]
                        sx, sy = bild.shape[1] / k.breite, bild.shape[0] / k.hoehe
                        p1 = (int(b["x"] * sx), int(b["y"] * sy))
                        p2 = (int((b["x"] + b["w"]) * sx), int((b["y"] + b["h"]) * sy))
                        cv2.rectangle(bild, p1, p2, (0, 255, 0), 3)
                    hoehe = round(960 * bild.shape[0] / bild.shape[1])
                    cv2.imshow(cid, cv2.resize(bild, (960, hoehe)))
                while not events.empty():
                    grund = nf.event(events.get())
                    if grund and not webcams:
                        print("ignoriert:", grund)
                meldung = nf.takt()
                if meldung:
                    print(meldung)
                if webcams:
                    if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                        break
                else:
                    time.sleep(0.02)
        except KeyboardInterrupt:
            pass
        finally:
            for cap in webcams.values():
                cap.release()
            if webcams:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
