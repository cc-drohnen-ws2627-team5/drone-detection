"""Tests fuer winkel.py. Start: python3 -m pytest test_winkel.py"""
import math

import numpy as np
import pytest

from winkel import (Achse, Kamera, Plattform, bbox_mitte, kalibriere_rotation,
                    korrektur_aus_tracking_bild, richtung, rotation_aus_ausrichtung,
                    strahl_zu_pan_tilt, winkelfehler_grad)


def test_bildmitte_ist_null():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    assert k.pixel_zu_pan_tilt(960, 540) == pytest.approx((0.0, 0.0), abs=1e-9)


def test_bildrand_ist_halbes_sichtfeld():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    pan, tilt = k.pixel_zu_pan_tilt(1920, 540)
    assert pan == pytest.approx(30.0)
    assert tilt == pytest.approx(0.0, abs=1e-9)
    pan, _ = k.pixel_zu_pan_tilt(0, 540)
    assert pan == pytest.approx(-30.0)


def test_oben_im_bild_ist_positiver_tilt():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    _, tilt = k.pixel_zu_pan_tilt(960, 0)
    assert tilt > 0
    assert tilt == pytest.approx(math.degrees(math.atan(540 / k.fy)))


def test_ausrichtung_verschiebt_bildmitte():
    k = Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(45, 20))
    assert k.pixel_zu_pan_tilt(960, 540) == pytest.approx((45.0, 20.0))


def test_rotation_ist_orthonormal_und_rechtshaendig():
    r = rotation_aus_ausrichtung(-37, 25, 8)
    assert r.T @ r == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(r) == pytest.approx(1.0)


@pytest.mark.parametrize("pan,tilt", [(0, 0), (12, -5), (-25, 18), (40, 30)])
def test_hin_und_zurueck(pan, tilt):
    k = Kamera.aus_sichtfeld(1920, 1080, 66, ausrichtung=(10, 15, 3))
    u, v = k.pan_tilt_zu_pixel(pan, tilt)
    assert k.pixel_zu_pan_tilt(u, v) == pytest.approx((pan, tilt), abs=1e-9)


def test_hinter_der_kamera_gibt_none():
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    assert k.pan_tilt_zu_pixel(180, 0) is None


def test_verzerrung_wird_herausgerechnet():
    k = Kamera(1920, 1080, 1400, 1400, 955, 545, verzerrung=(-0.3, 0.1, 0.001, -0.0005, 0.0))
    # Punkt mit bekannter Richtung kuenstlich verzerren (OpenCV-Modell) ...
    x, y = 0.35, -0.2
    k1, k2, p1, p2, k3 = k.verzerrung
    r2 = x * x + y * y
    radial = 1 + k1 * r2 + k2 * r2 ** 2 + k3 * r2 ** 3
    xd = x * radial + 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
    yd = y * radial + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
    u, v = k.cx + k.fx * xd, k.cy + k.fy * yd
    # ... und zurueckrechnen
    s = k.strahl_kamera(u, v)
    assert s[0] / s[2] == pytest.approx(x, abs=1e-6)
    assert s[1] / s[2] == pytest.approx(y, abs=1e-6)


def test_aus_opencv():
    km = [[1400, 0, 950], [0, 1390, 530], [0, 0, 1]]
    k = Kamera.aus_opencv(km, [0, 0, 0, 0], 1920, 1080)
    assert (k.fx, k.fy, k.cx, k.cy) == (1400, 1390, 950, 530)
    assert len(k.verzerrung) == 5
    assert k.pixel_zu_pan_tilt(950, 530) == pytest.approx((0, 0), abs=1e-9)


def test_kalibrierung_findet_rotation_wieder():
    wahr = rotation_aus_ausrichtung(30, 12, -4)
    k = Kamera.aus_sichtfeld(1920, 1080, 60)
    rng = np.random.default_rng(1)
    paare = []
    for u, v in [(200, 150), (1700, 200), (960, 540), (300, 950), (1650, 900), (1000, 100)]:
        s = k.strahl_kamera(u, v)
        pan, tilt = strahl_zu_pan_tilt(wahr @ s)
        paare.append((s, (pan + rng.normal(0, 0.2), tilt + rng.normal(0, 0.2))))  # Messfehler 0,2 Grad
    geschaetzt = kalibriere_rotation(paare)
    assert winkelfehler_grad(geschaetzt, paare) < 0.5
    # Die geschaetzte Drehung zeigt fast in dieselbe Richtung wie die wahre
    assert strahl_zu_pan_tilt(geschaetzt[:, 2]) == pytest.approx(strahl_zu_pan_tilt(wahr[:, 2]), abs=0.5)


def test_kalibrierung_braucht_drei_punkte():
    with pytest.raises(ValueError):
        kalibriere_rotation([((0, 0, 1), (0, 0))] * 2)


def test_servo_umrechnung_und_grenzen():
    p = Plattform(pan=Achse(mitte=90, richtung=-1), tilt=Achse(mitte=90, minimum=80, maximum=180))
    assert p.servo_winkel(20, 30) == (70, 120)
    assert p.move_befehl(20, 30) == "MOVE 70.0 120.0"
    assert p.servo_winkel(0, -40) == (90, 80)          # tilt am Anschlag begrenzt
    assert not p.erreichbar(0, -40)
    assert p.erreichbar(-80, 85)
    assert p.pan.von_servo(70) == 20


def test_bbox_mitte():
    assert bbox_mitte({"x": 412, "y": 128, "w": 36, "h": 22}) == (430, 139)


def test_korrektur_aus_tracking_bild():
    hq = Kamera.aus_sichtfeld(4056, 3040, 22.2)
    assert korrektur_aus_tracking_bild(2028, 1520, hq) == pytest.approx((0, 0), abs=1e-9)
    d_pan, d_tilt = korrektur_aus_tracking_bild(4056, 1520, hq)
    assert d_pan == pytest.approx(11.1)
    assert d_tilt == pytest.approx(0, abs=1e-9)


def _zwei_webcams():
    from winkel import KameraSystem
    return KameraSystem({
        "cam-1": Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(-25, 15)),
        "cam-2": Kamera.aus_sichtfeld(1920, 1080, 60, ausrichtung=(25, 15)),
    })


def test_zwei_webcams_waehlen_die_richtige_kamera():
    system = _zwei_webcams()
    mitte = {"x": 950, "y": 530, "w": 20, "h": 20}         # Bildmitte
    assert system.ziel_aus_event({"camera_id": "cam-1", "bbox": mitte}) == pytest.approx((-25, 15))
    assert system.ziel_aus_event({"camera_id": "cam-2", "bbox": mitte}) == pytest.approx((25, 15))
    with pytest.raises(KeyError):
        system.ziel_aus_event({"camera_id": "cam-9", "bbox": mitte})


def test_drohne_im_ueberlappungsbereich_beider_webcams():
    system = _zwei_webcams()
    ziel = (2.0, 20.0)                                      # in beiden Bildern sichtbar
    assert sorted(system.sieht(*ziel)) == ["cam-1", "cam-2"]
    events = []
    for cid, k in system.kameras.items():
        u, v = k.pan_tilt_zu_pixel(*ziel)
        events.append({"camera_id": cid, "bbox": {"x": u - 5, "y": v - 5, "w": 10, "h": 10}, "confidence": 0.8})
    assert system.ziel_aus_events(events) == pytest.approx(ziel, abs=1e-6)


def test_sichtbereich_luecken_finden():
    system = _zwei_webcams()
    assert system.sieht(0, 15) == ["cam-1", "cam-2"]
    assert system.sieht(-50, 15) == ["cam-1"]
    assert system.sieht(80, 15) == []                       # ausserhalb beider Webcams


def test_richtung_ist_einheitsvektor():
    assert np.linalg.norm(richtung(33, -12)) == pytest.approx(1.0)
