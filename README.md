# drone-detection
# Task 6 – Pan-Tilt Tracking

A platform with two servos automatically points the HQ camera at a drone that one of the fixed webcams has detected, and keeps it in the centre of the image.

- **Stage 1:** detection in the webcam image → pan/tilt angles → the platform turns roughly there.
- **Stage 2:** once the HQ camera sees the drone, it pulls it to the image centre itself and follows it. While that works, the webcams are ignored; if it loses the drone, the webcams take over again.

```
Webcams → detection (Task 1/2) → MQTT → pantilt_tracking.py → USB → Pico → servos
HQ camera ──────────────────────────→ pantilt_tracking.py (stage 2)
```

## Hardware

| Part | Details |
|---|---|
| Platform | 3D-printed mount (round base, fork), 2× Miuzei MS18 servo |
| Tracking camera | Raspberry Pi HQ Camera with 16 mm lens (22.2° × 16.7°), Standard–Mini cable on the Pi 5 |
| Fixed cameras | 2× LL1 USB webcam, 100° according to the maker (assumed: about 92° horizontal) |
| Microcontroller | Raspberry Pi Pico 2 W, USB to the Pi 5 |
| Servo power | HW-131 breadboard power module (5 V), ground connected to the Pico |
| Wiring | signal pan → GP15, tilt → GP14 |

**Measured servo angles:** pan 90 = straight ahead, larger = to the left. Tilt 90 = straight up, 180 = level to the front, 0 = level to the back. The software uses tilt 90–180.

## Files

| File | Purpose |
|---|---|
| `pico/main.py` | Firmware (v4). Commands: `MOVE <pan> <tilt>`, `SPEED`, `ACCEL`, `KICK`, `HOME`, `STOP`, `POS?` |
| `pi5/angles.py` | Maths: pixel → pan/tilt, calibration |
| `pi5/pantilt_control.py` | Connection to the Pico, settings (`CAMERAS`, `PLATFORM`), keyboard control |
| `pi5/pantilt_click.py` | Calibration: click into the webcam image, HQ window with crosshair |
| `pi5/pantilt_tracking.py` | Operation: detections via MQTT, motion demo, stage 2 with `--hq` |
| `pi5/pantilt_hq.py` | Stage 2: find the target in the HQ image and centre it |
| `pi5/tests/` | Tests without hardware: `python3 -m pytest tests` (in `pi5/`) |
| `hardware/` | OpenSCAD models of the mounts |

## Quick start (Pi 5)

1. Packages: `sudo apt install -y python3-serial python3-numpy python3-opencv python3-picamera2 v4l-utils python3-paho-mqtt`
2. Firmware: save `pico/main.py` to the Pico as `main.py` with Thonny, close Thonny.
3. Webcams: `v4l2-ctl --list-devices`, enter the paths in `pi5/pantilt_click.py` under `WEBCAM_DEVICES`.
4. Calibrate: `cd pi5`, then `python3 pantilt_click.py`. Press `m` for CALIBRATE mode, move the landmark into the HQ crosshair with `w a s d`, click the same landmark in the webcam image. 6 landmarks per webcam, far away (outdoors), then `c`. The result is saved in `calibration.json`.
5. Run:

| Command | Purpose |
|---|---|
| `python3 pantilt_tracking.py --motion` | demo: follows anything that moves in front of the webcams |
| `python3 pantilt_tracking.py --motion --hq color` | demo with stage 2, red object |
| `python3 pantilt_tracking.py --hq-only --hq color` | stage 2 only |
| `python3 pantilt_tracking.py --mqtt localhost --hq sky` | real operation with the drone detection |

## Done

- [x] Platform built, wired, running on the Pi 5
- [x] Firmware with smooth movement; directions and ranges measured
- [x] Calibration by clicking; estimates orientation, field of view and edge distortion of the webcams
- [x] Stage 1 on the Pi 5: clicking into the webcam image and the `--motion` demo work
- [x] Receiving detections via MQTT built in (not yet tested with the real detection)
- [x] Stage 2 and firmware v4 with start-up help written (**only tested in simulation**)

## Open

- [ ] **Tilt only lifts from level with a push by hand** and stutters while moving: counterweight behind the tilt axis, firmware v4, 5 V / 3 A power supply; otherwise a stronger tilt servo
- [ ] Test stage 2 and firmware v4 on the hardware
- [ ] Mount webcams and platform on one common base plate, then calibrate at a window with far-away landmarks (first try at home: 10.6° error because of close landmarks and about 1 m between webcams and platform)
- [ ] Test with the real detection of Task 2 via MQTT, set up the broker
- [ ] Looking over the top, so the platform can also aim behind itself (tilt 0–90)
- [ ] Status messages for the dashboard, autostart at power-up
- [ ] Log measurements for the documentation: error in degrees, time until the target is in the HQ image
- [ ] Optional: flight path prediction (Kalman filter) if measurements show the drone lags behind; countermeasure demonstrator

**Decided:** the camera turns on the first detection, not only after several confirmed frames.

## Message format (proposal)

Webcam detections to `sensors/pi5/detections`, several times per second while the drone is visible:

```json
{"camera_id": "cam-1", "class": "drone", "confidence": 0.9,
 "bbox": {"x": 900, "y": 300, "w": 60, "h": 40}, "track_id": 7, "timestamp": 1764160000.5}
```

`bbox` in pixels of the original image, `x`/`y` = top-left corner. Detections on the HQ image with `"camera_id": "hq"`.

## Open questions for the team

**Task 1 (sensor node, webcams)**
1. Your program opens the webcams, mine only gets the messages. OK? For calibrating, your detection has to be stopped for a short time.
2. Which image size does the detection get? I assume 1920 × 1080.
3. Which webcam is `cam-1`, which `cam-2`? Tip: always the same USB port, path under `/dev/v4l/by-path/`.
4. Where will the webcams be mounted? Build them onto one board together with the platform?

**Task 2 (drone detection)**
1. Detections via MQTT in the format above?
2. Exact class name for drones?
3. `track_id` possible (e.g. `model.track` in Ultralytics)?
4. Can the model also run on the HQ image? Otherwise I use my simple sky detector.
5. Messages continuously, not just once. Two topics: every detection (for me) and one stored event per drone (backend)?
6. `bbox` in pixels of the original image, not of the scaled model input?
7. Send the `timestamp` of the image capture (`time.time()`)?
8. Several drones: one message per drone or a list?
9. How many frames per second does the model manage?
10. MQTT broker on the Pi 5 (proposal), forwarding to the backend in the cluster?

**Task 4 (dashboard)**
1. What should be shown from the tracking? Offer: mode (webcam, HQ, home), pan/tilt, `track_id`, drone in the HQ image yes/no, later HQ snapshots.
2. Topic and rate? Proposal: `sensors/pi5/tracking`, once per second.

**Professor:** budget for a stronger tilt servo and a 5 V / 3 A power supply? Test drone, and may we fly on campus?

