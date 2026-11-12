"""Tests fuer pantilt_klick.py ohne Fenster und Kameras. Start: python3 -m pytest"""
import numpy as np
import pytest

from pantilt_klick import KlickSteuerung, fadenkreuz, fenster_zu_kamerapixel, kamerapixel_zu_fenster
from test_pantilt_steuerung import neue_steuerung
from winkel import Kamera, rotation_aus_ausrichtung, strahl_zu_pan_tilt


def test_klick_im_verkleinerten_fenster():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    # Fenster 960 x 540 zeigt ein 1920 x 1080-Bild: Faktor 2
    assert fenster_zu_kamerapixel(480, 270, (1920, 1080), (960, 540), k) == (960, 540)
    assert fenster_zu_kamerapixel(100, 50, (1920, 1080), (960, 540), k) == (200, 100)


def test_webcam_liefert_andere_aufloesung():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)        # eingetragen: Full HD
    # Webcam liefert nur 1280 x 720, Fenster 960 x 540
    assert fenster_zu_kamerapixel(480, 270, (1280, 720), (960, 540), k) == pytest.approx((960, 540))


def test_hin_und_zurueck_fenster():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    assert kamerapixel_zu_fenster(960, 540, (960, 540), k) == (480, 270)


def test_klick_im_zielmodus_faehrt_plattform(tmp_path):
    app = KlickSteuerung(neue_steuerung(tmp_path))
    app.klick("cam-2", 960, 540)                     # Bildmitte von cam-2 (pan +30, tilt +25)
    assert app.st.ser.befehle[-1] == "MOVE 120.0 115.0"
    assert (app.st.pan, app.st.tilt) == pytest.approx((30, 25))


def test_klick_im_kalibriermodus_speichert_punkt(tmp_path):
    app = KlickSteuerung(neue_steuerung(tmp_path))
    app.taste("m")
    assert app.modus == "KALIBRIEREN"
    vorher = list(app.st.ser.befehle)
    app.klick("cam-1", 500, 400)
    assert len(app.st.punkte["cam-1"]) == 1
    assert app.st.ser.befehle == vorher              # Plattform bleibt stehen


def test_kalibrieren_per_klick_end_to_end(tmp_path):
    app = KlickSteuerung(neue_steuerung(tmp_path))
    wahr = rotation_aus_ausrichtung(-33, 22, 1)
    k = app.st.system.kameras["cam-1"]
    app.taste("m")
    for u, v in [(150, 150), (1750, 200), (960, 540), (300, 950), (1650, 900)]:
        app.st.fahren(*strahl_zu_pan_tilt(wahr @ k.strahl_kamera(u, v)))   # HQ zeigt auf den Punkt
        app.klick("cam-1", u, v)                                           # Punkt im Webcam-Bild
    app.taste("c")
    assert "cam-1: Fehler 0.00" in app.st.meldung
    # Danach trifft ein Klick im Zielmodus genau die richtige Richtung
    app.taste("m")
    app.klick("cam-1", 1200, 300)
    assert (app.st.pan, app.st.tilt) == pytest.approx(strahl_zu_pan_tilt(wahr @ k.strahl_kamera(1200, 300)))


def test_tasten(tmp_path):
    app = KlickSteuerung(neue_steuerung(tmp_path))
    app.taste("d"); app.taste("w")
    assert (app.st.pan, app.st.tilt) == (2, 2)
    app.taste("+"); app.taste("a")
    assert app.st.pan == -2
    app.taste("h")
    assert (app.st.pan, app.st.tilt) == (0, 0)
    assert app.taste("q") is False and app.taste("\x1b") is False


def test_fehler_wird_angezeigt_statt_absturz(tmp_path):
    app = KlickSteuerung(neue_steuerung(tmp_path))
    assert app.klick("cam-7", 1, 2).startswith("Fehler")


def test_overlay_und_fadenkreuz_zeichnen(tmp_path):
    app = KlickSteuerung(neue_steuerung(tmp_path))
    app.klick("cam-2", 1000, 600)                    # Klick faehrt die Plattform dorthin ...
    app.st.fahren(30, 25)                            # ... dann zurueck auf die Bildmitte von cam-2
    bild = np.zeros((540, 960, 3), np.uint8)
    app.overlay(bild, "cam-2")
    assert bild[270, 480 + 14 - 1:480 + 14 + 2, 2].max() == 255   # roter Kreis um die Bildmitte
    assert fadenkreuz(np.zeros((760, 1014, 3), np.uint8)).any()
