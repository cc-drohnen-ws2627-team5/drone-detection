"""Tests fuer die Logik von pantilt_steuerung.py, mit simuliertem Pico. Start: python3 -m pytest"""
import json

import numpy as np
import pytest

from pantilt_steuerung import Steuerung
from winkel import Achse, Kamera, Plattform, rotation_aus_ausrichtung, strahl_zu_pan_tilt


class PicoAttrappe:
    """Antwortet wie main.py auf dem Pico."""
    def __init__(self):
        self.befehle = []
        self._antwort = b""

    def reset_input_buffer(self):
        self._antwort = b""

    def write(self, daten):
        befehl = daten.decode().strip()
        self.befehle.append(befehl)
        self._antwort = b"POS 90.0 90.0\r\n" if befehl == "POS?" else b"OK\r\n"

    def readline(self):
        return self._antwort


def neue_steuerung(tmp_path, **kw):
    kameras = {
        "cam-1": Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(-30, 25)),
        "cam-2": Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(30, 25)),
    }
    plattform = Plattform(pan=Achse(mitte=90), tilt=Achse(mitte=90))
    return Steuerung(PicoAttrappe(), kameras, plattform, tmp_path / "kalibrierung.json", **kw)


def test_pfeiltasten_senden_move(tmp_path):
    st = neue_steuerung(tmp_path)
    assert st.schritt(5, -2) == "OK"
    assert st.ser.befehle[-1] == "MOVE 95.0 88.0"


def test_ziel_aus_webcam_pixel(tmp_path):
    st = neue_steuerung(tmp_path)
    meldung = st.ziel("cam-2 960 540")                 # Bildmitte von cam-2
    assert st.ser.befehle[-1] == "MOVE 120.0 115.0"     # pan +30, tilt +25
    assert "OK" in meldung


def test_unerreichbares_ziel_wird_nicht_gesendet(tmp_path):
    st = neue_steuerung(tmp_path)
    vorher = list(st.ser.befehle)
    assert "nicht erreichbar" in st.fahren(120, 0)
    assert st.ser.befehle == vorher


@pytest.mark.parametrize("eingabe", ["cam-1 960", "cam-7 1 2", "cam-1 a b"])
def test_falsche_eingaben(tmp_path, eingabe):
    st = neue_steuerung(tmp_path)
    with pytest.raises(ValueError):
        st.ziel(eingabe)


def test_kalibrierung_end_to_end(tmp_path):
    st = neue_steuerung(tmp_path)
    wahr = rotation_aus_ausrichtung(-34, 21, 2)          # echte Lage weicht von der Schaetzung ab
    k = st.system.kameras["cam-1"]
    for u, v in [(200, 200), (1700, 250), (960, 540), (400, 900), (1600, 850)]:
        pan, tilt = strahl_zu_pan_tilt(wahr @ k.strahl_kamera(u, v))
        st.fahren(pan, tilt)                             # Tracking-Kamera zeigt auf den Punkt
        st.kalibrierpunkt(f"cam-1 {u} {v}")
    meldung = st.kalibrieren()
    assert "cam-1: Fehler 0.00" in meldung and "cam-2: 0/3" in meldung
    assert np.allclose(k.rotation, wahr, atol=1e-6)

    # Datei wird beim naechsten Start geladen
    daten = json.loads((tmp_path / "kalibrierung.json").read_text())
    assert set(daten) == {"cam-1"}
    neu = neue_steuerung(tmp_path)
    assert "cam-1" in neu.meldung
    assert np.allclose(neu.system.kameras["cam-1"].rotation, wahr, atol=1e-6)
