"""AERO Observer - Drohnen-Monitor im iOS-Stil (Tkinter, keine neuen Pakete nötig).

Start:  python aero_observer.py --weights best.pt --cameras 0 1 2
Hilfe:  python aero_observer.py --help
"""
import argparse
import collections
import os
import platform
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageTk

try:
    import psutil
except ImportError:
    psutil = None

IS_WIN = platform.system() == 'Windows'
BOX_MAX_AGE = 0.8       # Boxen nur zeigen, wenn die KI-Auswertung nicht älter ist
ORANGE_BGR = (10, 159, 255)

BG, CARD, CARD2 = '#000000', '#1c1c1e', '#2c2c2e'
INK, DIM = '#ffffff', '#8e8e93'
BLUE, GREEN, ORANGE, RED = '#0a84ff', '#30d158', '#ff9f0a', '#ff453a'
FAMILY = 'Helvetica'


def F(size, bold=False):
    """Schrift in Pixeln (negative Größe), damit das Layout überall gleich bleibt."""
    return (FAMILY, -size, 'bold' if bold else 'normal')


def rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return '#%02x%02x%02x' % tuple(int(x + (y - x) * t) for x, y in zip(rgb(a), rgb(b)))


def round_points(x1, y1, x2, y2, r):
    """Punkte für ein abgerundetes Rechteck (Canvas-Polygon mit smooth=True)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
            x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
            x1, y1 + r, x1, y1]


def label(parent, text='', size=13, color=INK, bold=False, bg=CARD, **kw):
    return tk.Label(parent, text=text, bg=bg, fg=color, font=F(size, bold),
                    anchor='w', justify='left', **kw)


# ----------------------------------------------------------------- Kamera
class CsiCapture:
    """Minimale VideoCapture-Hülle für CSI-Kameras (Picamera2, nur Raspberry Pi)."""

    def __init__(self, index):
        self.cam = None
        try:
            from picamera2 import Picamera2
            self.cam = Picamera2(index)
            # 'RGB888' liefert in Picamera2 die Byte-Reihenfolge B,G,R = OpenCV-kompatibel.
            self.cam.configure(self.cam.create_video_configuration(
                main={'size': (640, 480), 'format': 'RGB888'}))
            self.cam.start()
        except Exception:
            self.cam = None

    def isOpened(self):
        return self.cam is not None

    def set(self, *args):
        return False

    def read(self):
        try:
            return True, self.cam.capture_array()
        except Exception:
            return False, None

    def release(self):
        if self.cam is not None:
            try:
                self.cam.stop()
                self.cam.close()
            except Exception:
                pass


class Camera:
    def __init__(self, source, name, stop):
        self.source, self.name, self.stop = source, name, stop
        self.lock = threading.Lock()
        self.frame, self.sequence, self.timestamp = None, 0, 0.0
        self.status, self.capture_fps = 'Verbinde …', 0.0
        self.thread = threading.Thread(target=self.run, daemon=True)

    def latest(self):
        with self.lock:
            return (self.frame, self.sequence, self.timestamp,
                    self.status, self.capture_fps)

    def open(self):
        if isinstance(self.source, int):
            return cv2.VideoCapture(self.source, cv2.CAP_DSHOW if IS_WIN else cv2.CAP_V4L2)
        if self.source.startswith('csi:'):
            return CsiCapture(int(self.source[4:]))
        if self.source.startswith('/dev/video'):
            return cv2.VideoCapture(self.source, cv2.CAP_V4L2)
        return cv2.VideoCapture(self.source)  # RTSP / HTTP / Datei

    def run(self):
        # Nur dieser Thread besitzt und schließt das Kamera-Handle.
        while not self.stop.is_set():
            capture = None
            try:
                capture = self.open()
                if not capture.isOpened():
                    raise RuntimeError('Nicht verfügbar')
                capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                capture.set(cv2.CAP_PROP_FPS, 30)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                previous = None
                while not self.stop.is_set():
                    ok, frame = capture.read()
                    if not ok:
                        raise RuntimeError('Verbindung unterbrochen')
                    now = time.perf_counter()
                    with self.lock:
                        if previous is not None:
                            rate = 1 / max(now - previous, 1e-6)
                            self.capture_fps = rate if not self.capture_fps \
                                else 0.9 * self.capture_fps + 0.1 * rate
                        self.frame, self.timestamp = frame, now
                        self.sequence += 1
                        self.status = f'{frame.shape[1]}×{frame.shape[0]}'
                    previous = now
            except Exception as error:
                with self.lock:
                    self.status, self.frame, self.capture_fps = str(error), None, 0.0
            finally:
                if capture is not None:
                    capture.release()
            self.stop.wait(2)


# --------------------------------------------------------------------- KI
class Engine:
    """Inferenz-Thread: wechselt reihum zwischen den Kameras."""

    def __init__(self, cameras, args, stop):
        self.cameras, self.args, self.stop = cameras, args, stop
        self.lock = threading.Lock()
        self.mode, self.paused, self.generation = -1, False, 0
        self.confidence = args.conf
        self.ready, self.status, self.names = False, 'Modell wird geladen …', {}
        self.results = [None] * len(cameras)
        self.thread = threading.Thread(target=self.run, daemon=True)

    def _reset(self):
        self.generation += 1
        self.results = [None] * len(self.cameras)

    def set_mode(self, mode):
        with self.lock:
            self.mode = mode
            self._reset()

    def set_paused(self, paused):
        with self.lock:
            self.paused = paused
            self._reset()

    def set_confidence(self, value):
        with self.lock:
            self.confidence = value
            self._reset()

    def snapshot(self):
        with self.lock:
            return (list(self.results), self.mode, self.paused,
                    self.ready, self.status, dict(self.names))

    def run(self):
        try:
            import torch
            from ultralytics import YOLO
            model = YOLO(str(self.args.weights), task='detect')
            try:
                model.fuse()
            except Exception:
                pass  # exportierte Modelle (NCNN/ONNX) brauchen kein fuse
            device, imgsz = self.args.device, self.args.imgsz
            model.predict(np.zeros((480, 640, 3), np.uint8), imgsz=imgsz,
                          device=device, verbose=False)
            torch.set_num_threads(self.args.threads)  # Ultralytics ändert das beim Warm-up
            with self.lock:
                self.ready, self.status = True, 'Modell bereit'
                self.names = dict(model.names)
            sequences = [-1] * len(self.cameras)
            previous = [None] * len(self.cameras)
            seen_generation, cursor = -1, 0
            while not self.stop.is_set():
                with self.lock:
                    mode, paused = self.mode, self.paused
                    confidence, generation = self.confidence, self.generation
                if generation != seen_generation:
                    sequences = [-1] * len(self.cameras)
                    previous = [None] * len(self.cameras)
                    seen_generation = generation
                if paused:
                    self.stop.wait(0.05)
                    continue
                positions = list(range(len(self.cameras))) if mode == -1 else [mode]
                position = positions[cursor % len(positions)]
                cursor += 1
                frame, sequence, stamp, _, _ = self.cameras[position].latest()
                if frame is None or sequence == sequences[position] \
                        or time.perf_counter() - stamp > 1:
                    self.stop.wait(0.005)
                    continue
                result = model.predict(frame.copy(), imgsz=imgsz, conf=confidence,
                                       device=device, verbose=False)[0]
                now = time.perf_counter()
                boxes = result.boxes.data.cpu().numpy().copy()
                fps = 0.0 if previous[position] is None else 1 / max(now - previous[position], 1e-6)
                previous[position] = now
                sequences[position] = sequence
                with self.lock:
                    if generation != self.generation or self.stop.is_set():
                        continue
                    old = self.results[position]
                    if old is not None and fps:
                        fps = 0.8 * old['fps'] + 0.2 * fps
                    self.results[position] = dict(
                        boxes=boxes, stamp=stamp, fps=fps, shape=frame.shape[:2],
                        inference=result.speed.get('inference', 0.0))
        except Exception as error:
            with self.lock:
                self.ready, self.status = False, f'Modellfehler: {error}'


# ---------------------------------------------------------------- Widgets
class RoundCard(tk.Canvas):
    """Abgerundete Karte. Inhalt kommt in `self.inner` (ein normaler Frame)."""

    def __init__(self, parent, radius=20, fill=CARD, pad=16, bg=BG, width=10, height=10):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, width=width, height=height)
        self.radius, self.fill, self.pad, self._outline = radius, fill, pad, fill
        self.shape = self.create_polygon(0, 0, 0, 0, smooth=True, fill=fill, outline=fill, width=2)
        self.inner = tk.Frame(self, bg=fill)
        self.window = self.create_window(pad, pad, anchor='nw', window=self.inner)
        self.bind('<Configure>', self._layout)

    def _layout(self, event):
        self.coords(self.shape, *round_points(1, 1, event.width - 1, event.height - 1, self.radius))
        self.coords(self.window, self.pad, self.pad)
        self.itemconfigure(self.window, width=max(1, event.width - 2 * self.pad),
                           height=max(1, event.height - 2 * self.pad))

    def set_outline(self, color=None):
        color = color or self.fill
        if color != self._outline:
            self._outline = color
            self.itemconfigure(self.shape, outline=color)


class RoundButton(tk.Canvas):
    def __init__(self, parent, text, command, bg=BG, fill=CARD2, hover='#3a3a3c'):
        font = F(13, True)
        width = tkfont.Font(font=font).measure(text) + 38
        super().__init__(parent, width=width, height=36, bg=bg, highlightthickness=0, cursor='hand2')
        self.fill, self.hover, self.command = fill, hover, command
        self.shape = self.create_polygon(round_points(1, 1, width - 1, 35, 12), smooth=True,
                                         fill=fill, outline=fill)
        self.create_text(width / 2, 18, text=text, fill=INK, font=font)
        self.bind('<Enter>', lambda e: self.paint(hover))
        self.bind('<Leave>', lambda e: self.paint(fill))
        self.bind('<ButtonPress-1>', lambda e: self.paint('#48484a'))
        self.bind('<ButtonRelease-1>', self.release)

    def paint(self, color):
        self.itemconfigure(self.shape, fill=color, outline=color)

    def release(self, event):
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self.paint(self.hover if inside else self.fill)
        if inside:
            self.command()


class Segmented(tk.Canvas):
    """iOS-Segmentauswahl mit gleitender Markierung."""

    def __init__(self, parent, options, command, bg=BG):
        self.font = F(13, True)
        measure = tkfont.Font(font=self.font).measure
        self.widths = [measure(o) + 34 for o in options]
        total = sum(self.widths) + 6
        super().__init__(parent, width=total, height=38, bg=bg, highlightthickness=0, cursor='hand2')
        self.command, self.index, self.job = command, 0, None
        self.create_polygon(round_points(1, 1, total - 1, 37, 12), smooth=True, fill=CARD, outline=CARD)
        self.starts, x = [], 3
        for width in self.widths:
            self.starts.append(x)
            x += width
        self.x, self.w = float(self.starts[0]), float(self.widths[0])
        self.highlight = self.create_polygon(round_points(self.x, 3, self.x + self.w, 35, 10),
                                             smooth=True, fill='#636366', outline='#636366')
        self.texts = [self.create_text(s + w / 2, 19, text=o, font=self.font, fill=INK if i == 0 else DIM)
                      for i, (o, s, w) in enumerate(zip(options, self.starts, self.widths))]
        self.bind('<Button-1>', self.click)

    def click(self, event):
        for i, (start, width) in enumerate(zip(self.starts, self.widths)):
            if start <= event.x < start + width:
                self.select(i, notify=True)
                return

    def select(self, index, notify=False):
        self.index = index
        for i, item in enumerate(self.texts):
            self.itemconfigure(item, fill=INK if i == index else DIM)
        if self.job is None:
            self.animate()
        if notify:
            self.command(index)

    def animate(self):
        tx, tw = self.starts[self.index], self.widths[self.index]
        self.x += (tx - self.x) * 0.4
        self.w += (tw - self.w) * 0.4
        done = abs(tx - self.x) < 0.5 and abs(tw - self.w) < 0.5
        if done:
            self.x, self.w = float(tx), float(tw)
        self.coords(self.highlight, *round_points(self.x, 3, self.x + self.w, 35, 10))
        self.job = None if done else self.after(16, self.animate)


class Toggle(tk.Canvas):
    """iOS-Schalter mit Animation."""

    def __init__(self, parent, value=True, command=None, bg=CARD):
        super().__init__(parent, width=51, height=31, bg=bg, highlightthickness=0, cursor='hand2')
        self.value, self.command, self.job = value, command, None
        self.t = 1.0 if value else 0.0
        self.bind('<Button-1>', lambda e: self.toggle())
        self.draw()

    def draw(self):
        self.delete('all')
        color = mix('#39393d', GREEN, self.t)
        self.create_oval(0, 0, 31, 31, fill=color, outline=color)
        self.create_oval(20, 0, 51, 31, fill=color, outline=color)
        self.create_rectangle(15, 0, 36, 31, fill=color, outline=color)
        x = 2 + 20 * self.t
        self.create_oval(x, 2, x + 27, 29, fill='white', outline='')

    def toggle(self):
        self.value = not self.value
        if self.job is None:
            self.animate()
        if self.command:
            self.command(self.value)

    def animate(self):
        target = 1.0 if self.value else 0.0
        self.t += (target - self.t) * 0.45
        done = abs(target - self.t) < 0.02
        if done:
            self.t = target
        self.draw()
        self.job = None if done else self.after(16, self.animate)


class Slider(tk.Canvas):
    def __init__(self, parent, low, high, value, command, bg=CARD):
        super().__init__(parent, height=30, bg=bg, highlightthickness=0, cursor='hand2')
        self.low, self.high, self.value, self.command = low, high, value, command
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Button-1>', self.drag)
        self.bind('<B1-Motion>', self.drag)

    def draw(self):
        w, pad = self.winfo_width(), 14
        if w < 2 * pad + 4:
            return
        x = pad + (self.value - self.low) / (self.high - self.low) * (w - 2 * pad)
        self.delete('all')
        self.create_polygon(round_points(pad, 13, w - pad, 17, 2), smooth=True, fill='#39393d', outline='')
        self.create_polygon(round_points(pad, 13, max(pad + 4, x), 17, 2), smooth=True, fill=BLUE, outline='')
        self.create_oval(x - 13, 3, x + 13, 29, fill='#0b0b0c', outline='')
        self.create_oval(x - 12, 2, x + 12, 28, fill='white', outline='')

    def drag(self, event):
        w, pad = self.winfo_width(), 14
        ratio = min(1.0, max(0.0, (event.x - pad) / max(1, w - 2 * pad)))
        value = int(round(self.low + ratio * (self.high - self.low)))
        if value != self.value:
            self.value = value
            self.draw()
            self.command(value)


class Pill(tk.Canvas):
    def __init__(self, parent, bg=CARD):
        super().__init__(parent, width=80, height=22, bg=bg, highlightthickness=0)
        self.page, self.key, self.font = bg, None, F(11, True)
        self.measure = tkfont.Font(font=self.font).measure

    def set(self, text, color):
        if (text, color) == self.key:
            return
        self.key = (text, color)
        width = self.measure(text) + 24
        tint = mix(self.page, color, 0.22)
        self.configure(width=width)
        self.delete('all')
        self.create_polygon(round_points(1, 1, width - 1, 21, 10), smooth=True, fill=tint, outline=tint)
        self.create_text(width / 2, 11, text=text, fill=color, font=self.font)


class StatusDot(tk.Canvas):
    def __init__(self, parent, bg=CARD):
        super().__init__(parent, width=24, height=24, bg=bg, highlightthickness=0)
        self.page = bg

    def set_state(self, color, phase):
        self.delete('all')
        radius = 6 + 5 * phase
        halo = mix(self.page, color, 0.35 * (1 - phase))
        self.create_oval(12 - radius, 12 - radius, 12 + radius, 12 + radius, fill=halo, outline='')
        self.create_oval(7, 7, 17, 17, fill=color, outline='')


class StatTile(RoundCard):
    def __init__(self, parent, caption):
        super().__init__(parent, radius=14, fill=CARD2, pad=12, bg=CARD, height=66)
        label(self.inner, caption, 11, DIM, bg=CARD2).pack(anchor='w')
        self.value = label(self.inner, '–', 20, INK, True, bg=CARD2)
        self.value.pack(anchor='w')

    def set(self, text):
        if self.value.cget('text') != text:
            self.value.configure(text=text)


class Sparkline(tk.Canvas):
    def __init__(self, parent, length=60, bg=CARD):
        super().__init__(parent, height=80, bg=bg, highlightthickness=0)
        self.page, self.length = bg, length
        self.values = collections.deque(maxlen=length)
        self.bind('<Configure>', lambda e: self.draw())

    def push(self, value):
        self.values.append(value)
        self.draw()

    def draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        self.delete('all')
        base, top = h - 4, max(3, max(self.values, default=0))
        self.create_line(0, base, w, base, fill=CARD2)
        if len(self.values) < 2:
            return
        offset, points = self.length - len(self.values), []
        for i, value in enumerate(self.values):
            points += [(offset + i) / (self.length - 1) * w, 4 + (h - 8) * (1 - value / top)]
        self.create_polygon([points[0], base] + points + [points[-2], base],
                            fill=mix(self.page, BLUE, 0.28), outline='')
        self.create_line(points, fill=BLUE, width=2.5, capstyle='round', joinstyle='round')


class EventLog(tk.Text):
    def __init__(self, parent, bg=CARD):
        super().__init__(parent, bg=bg, fg=INK, bd=0, highlightthickness=0, wrap='word',
                         font=F(12), cursor='arrow', padx=0, pady=0, width=10, height=4)
        self.tag_configure('head', font=F(13, True), spacing1=8)
        self.tag_configure('sub', foreground=DIM, font=F(12), spacing3=2)
        self.tag_configure('empty', foreground=DIM)
        self.empty = True
        self.insert('1.0', 'Noch keine Erkennungen', 'empty')
        self.configure(state='disabled')

    def add(self, head, sub):
        self.configure(state='normal')
        if self.empty:
            self.delete('1.0', 'end')
            self.empty = False
        self.insert('1.0', head + '\n', 'head', sub + '\n', 'sub')
        if int(self.index('end-1c').split('.')[0]) > 300:
            self.delete('301.0', 'end')
        self.configure(state='disabled')


class Tile(RoundCard):
    def __init__(self, parent, name, on_click):
        super().__init__(parent, radius=20, pad=14)
        head = tk.Frame(self.inner, bg=CARD)
        head.pack(fill='x')
        label(head, name, 15, INK, True).pack(side='left')
        self.pill = Pill(head)
        self.pill.pack(side='right')
        self.canvas = tk.Canvas(self.inner, bg=CARD, highlightthickness=0, width=120, height=90,
                                cursor='hand2')
        self.canvas.pack(fill='both', expand=True, pady=8)
        self.image_item = self.canvas.create_image(0, 0, anchor='center')
        self.empty_item = self.canvas.create_text(0, 0, text='Kein Signal', fill=DIM, font=F(14))
        self.canvas.bind('<Configure>', self.center)
        self.canvas.bind('<Button-1>', lambda e: on_click())
        self.info = label(self.inner, 'Verbinde …', 12, DIM)
        self.info.pack(fill='x')
        self.photo = self.photo_size = self.key = None

    def center(self, event):
        self.canvas.coords(self.empty_item, event.width // 2, event.height // 2)
        self.canvas.coords(self.image_item, event.width // 2, event.height // 2)

    def clear_video(self):
        if self.key is not None or self.photo is not None:
            self.canvas.itemconfigure(self.image_item, image='')
            self.canvas.itemconfigure(self.empty_item, state='normal')
            self.photo = self.photo_size = self.key = None


# ----------------------------------------------------------------- Monitor
class Monitor:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.stop = threading.Event()
        self.started = time.perf_counter()
        sources = [int(s) if s.isdigit() else s for s in args.cameras]
        names = args.names or []
        self.cameras = [Camera(src, names[i] if i < len(names) else f'Kamera {i + 1}', self.stop)
                        for i, src in enumerate(sources)]
        self.engine = Engine(self.cameras, args, self.stop)
        n = len(self.cameras)
        self.prev_count, self.last_event = [0] * n, [0.0] * n
        self.events, self.overlay, self.closed = 0, True, False
        self.last_sample = self.last_sys = 0.0
        self.sys_text, self.notice = ('–', '–'), ('', 0.0)
        self.model_text, self.masks = '', {}
        self.card_rgb = rgb(CARD)
        if args.snapshots:
            args.snapshots.mkdir(parents=True, exist_ok=True)
        self.build()
        for camera in self.cameras:
            camera.thread.start()
        self.engine.thread.start()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<F11>', lambda e: self.toggle_fullscreen())
        root.bind('<Escape>', lambda e: self.leave_fullscreen())
        root.bind('<space>', lambda e: self.ai_toggle.toggle())
        root.bind('<q>', lambda e: self.close())
        root.after(40, self.refresh)

    # ---- Aufbau
    def build(self):
        root = self.root
        root.title('AERO Observer')
        root.geometry('1360x850')
        root.minsize(1150, 720)
        root.configure(bg=BG)

        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=24, pady=(20, 14))
        left = tk.Frame(header, bg=BG)
        left.pack(side='left')
        label(left, 'Observer', 28, INK, True, bg=BG).pack(anchor='w')
        self.clock = label(left, '', 12, DIM, bg=BG)
        self.clock.pack(anchor='w')
        self.segmented = Segmented(header, ['Alle'] + [c.name for c in self.cameras], self.on_mode)
        self.segmented.pack(side='left', padx=30)
        for text, action in [('Beenden', self.close), ('Vollbild', self.toggle_fullscreen),
                             ('Screenshot', self.manual_snapshot)]:
            RoundButton(header, text, action).pack(side='right', padx=(10, 0))

        body = tk.Frame(root, bg=BG)
        body.pack(fill='both', expand=True, padx=24, pady=(0, 22))
        side = tk.Frame(body, bg=BG, width=340)
        side.pack(side='right', fill='y', padx=(12, 0))
        side.pack_propagate(False)
        grid = tk.Frame(body, bg=BG)
        grid.pack(side='left', fill='both', expand=True)
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform='col')
        for r in range(2):
            grid.rowconfigure(r, weight=1, uniform='row')

        n = len(self.cameras)
        cells = {1: [(0, 0, 2)], 2: [(0, 0, 1), (0, 1, 1)],
                 3: [(0, 0, 1), (0, 1, 1), (1, 0, 1)]}[n]
        self.tiles = []
        for i, (row, column, span) in enumerate(cells):
            tile = Tile(grid, self.cameras[i].name, lambda i=i: self.focus(i))
            tile.grid(row=row, column=column, columnspan=span, sticky='nsew', padx=6, pady=6)
            self.tiles.append(tile)
        activity = RoundCard(grid, radius=20, pad=16)
        row, column, span = (1, 1, 1) if n == 3 else (1, 0, 2)
        activity.grid(row=row, column=column, columnspan=span, sticky='nsew', padx=6, pady=6)
        label(activity.inner, 'ERKENNUNGEN · LETZTE 60 SEKUNDEN', 11, DIM).pack(fill='x')
        self.spark = Sparkline(activity.inner)
        self.spark.pack(fill='x', pady=(4, 8))
        label(activity.inner, 'EREIGNISSE', 11, DIM).pack(fill='x')
        self.log = EventLog(activity.inner)
        self.log.pack(fill='both', expand=True)

        self.build_sidebar(side)

    def build_sidebar(self, side):
        status = RoundCard(side, radius=20, pad=16, height=92)
        status.pack(fill='x', pady=(6, 12))
        self.dot = StatusDot(status.inner)
        self.dot.pack(side='left', padx=(0, 12))
        texts = tk.Frame(status.inner, bg=CARD)
        texts.pack(side='left', fill='x', expand=True)
        self.alert = label(texts, 'Starte …', 21, INK, True)
        self.alert.pack(fill='x')
        self.subtitle = label(texts, '', 12, DIM)
        self.subtitle.pack(fill='x')

        grid = tk.Frame(side, bg=BG)
        grid.pack(fill='x', pady=(0, 12))
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform='stat')
        self.stats = {}
        for i, key in enumerate(['KI FPS', 'Latenz', 'Kameras', 'Ereignisse', 'CPU Temp', 'CPU Last']):
            self.stats[key] = StatTile(grid, key)
            self.stats[key].grid(row=i // 2, column=i % 2, sticky='ew',
                                 padx=(0, 5) if i % 2 == 0 else (5, 0), pady=5)

        controls = RoundCard(side, radius=20, pad=16, height=206)
        controls.pack(fill='x', pady=(0, 12))
        inner = controls.inner
        def make_toggle(text, command):
            line = tk.Frame(inner, bg=CARD)
            line.pack(fill='x', pady=(0, 12))
            label(line, text, 15, INK, True).pack(side='left')
            toggle = Toggle(line, True, command)
            toggle.pack(side='right')
            return toggle

        self.ai_toggle = make_toggle('KI-Erkennung', lambda on: self.engine.set_paused(not on))
        self.box_toggle = make_toggle('Boxen anzeigen', lambda on: setattr(self, 'overlay', on))
        row = tk.Frame(inner, bg=CARD)
        row.pack(fill='x')
        label(row, 'Konfidenz', 15, INK, True).pack(side='left')
        self.conf_value = label(row, f'{self.args.conf:.0%}', 13, DIM)
        self.conf_value.pack(side='right')
        Slider(inner, 10, 90, int(self.args.conf * 100), self.on_confidence).pack(fill='x', pady=(6, 0))

        model = RoundCard(side, radius=20, pad=16)
        model.pack(fill='both', expand=True)
        label(model.inner, 'MODELL', 11, DIM).pack(fill='x')
        self.model_info = label(model.inner, '', 12, INK, wraplength=290)
        self.model_info.pack(fill='x', pady=(6, 0))

    # ---- Aktionen
    def on_mode(self, index):
        self.engine.set_mode(index - 1)

    def focus(self, i):
        self.segmented.select(0 if self.segmented.index == i + 1 else i + 1, notify=True)

    def on_confidence(self, value):
        self.conf_value.configure(text=f'{value} %')
        self.engine.set_confidence(value / 100)

    def toggle_fullscreen(self):
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))

    def leave_fullscreen(self):
        if self.root.attributes('-fullscreen'):
            self.root.attributes('-fullscreen', False)
        else:
            self.close()

    def save_snapshot(self, index, frame, state, reason):
        if not self.args.snapshots or frame is None:
            return None
        image = frame.copy()
        if state is not None and state['shape'] == image.shape[:2]:
            for x1, y1, x2, y2, *_ in state['boxes']:
                cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), ORANGE_BGR, 2)
        path = self.args.snapshots / f'{datetime.now():%Y%m%d_%H%M%S}_cam{index + 1}_{reason}.jpg'
        cv2.imwrite(str(path), image)
        return path

    def manual_snapshot(self):
        results = self.engine.snapshot()[0]
        saved = sum(1 for i, c in enumerate(self.cameras)
                    if self.save_snapshot(i, c.latest()[0], results[i], 'manuell'))
        self.notice = (f'{saved} Screenshot(s) gespeichert', time.perf_counter() + 3)

    def read_system(self):
        temp = '–'
        try:
            temp = f'{int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000:.0f} °C'
        except (OSError, ValueError):
            pass
        if psutil:
            load = f'{psutil.cpu_percent():.0f} %'
        elif hasattr(os, 'getloadavg'):
            load = f'{min(100, os.getloadavg()[0] / (os.cpu_count() or 1) * 100):.0f} %'
        else:
            load = '–'
        self.sys_text = (temp, load)

    # ---- Darstellung
    def mask_for(self, w, h, radius=14):
        mask = self.masks.get((w, h))
        if mask is None:
            if len(self.masks) > 24:
                self.masks.clear()
            big = Image.new('L', (w * 3, h * 3), 0)
            ImageDraw.Draw(big).rounded_rectangle([0, 0, w * 3 - 1, h * 3 - 1], radius=radius * 3, fill=255)
            mask = self.masks[(w, h)] = big.resize((w, h), Image.LANCZOS)
        return mask

    def draw_video(self, tile, frame, seq, state, boxes, names, alert):
        cw, ch = max(1, tile.canvas.winfo_width()), max(1, tile.canvas.winfo_height())
        key = (seq, id(state), cw, ch, boxes is not None, alert)
        if key == tile.key:
            return
        tile.key = key
        h, w = frame.shape[:2]
        scale = min(cw / w, ch / h, 1.0)
        pw, ph = max(2, int(w * scale)), max(2, int(h * scale))
        preview = cv2.resize(frame, (pw, ph),
                             interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        if boxes is not None:
            for x1, y1, x2, y2, conf, cls in boxes:
                p1, p2 = (int(x1 * scale), int(y1 * scale)), (int(x2 * scale), int(y2 * scale))
                cv2.rectangle(preview, p1, p2, ORANGE_BGR, 2, cv2.LINE_AA)
                text = f'{names.get(int(cls), "Objekt")} {conf:.0%}'
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                top = max(0, p1[1] - th - 10)
                cv2.rectangle(preview, (p1[0], top), (p1[0] + tw + 12, top + th + 10), ORANGE_BGR, -1)
                cv2.putText(preview, text, (p1[0] + 6, top + th + 4), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 0, 0), 1, cv2.LINE_AA)
        picture = Image.new('RGB', (pw, ph), self.card_rgb)
        picture.paste(Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)), (0, 0),
                      self.mask_for(pw, ph))
        if tile.photo is not None and tile.photo_size == (pw, ph):
            tile.photo.paste(picture)
        else:
            tile.photo, tile.photo_size = ImageTk.PhotoImage(picture), (pw, ph)
        tile.canvas.itemconfigure(tile.image_item, image=tile.photo)
        tile.canvas.itemconfigure(tile.empty_item, state='hidden')
        tile.canvas.coords(tile.image_item, cw // 2, ch // 2)

    def refresh(self):
        if self.closed:
            return
        t0 = time.perf_counter()
        results, mode, paused, ready, status, names = self.engine.snapshot()
        online, total_fps, total_boxes, latencies = 0, 0.0, 0, []
        for i, camera in enumerate(self.cameras):
            frame, seq, stamp, cam_status, cap_fps = camera.latest()
            connected = frame is not None and t0 - stamp < 1.5
            state = results[i]
            age = None if state is None else t0 - state['stamp']
            selected = mode in (-1, i)
            fresh = connected and selected and ready and not paused and age is not None and age < 2
            count, conf, boxes = 0, 0.0, None
            if fresh:
                total_fps += state['fps']
                latencies.append(state['inference'])
                if len(state['boxes']) and age < 1.5:
                    count, conf = len(state['boxes']), float(state['boxes'][:, 4].max())
                if age <= BOX_MAX_AGE and state['shape'] == frame.shape[:2] and self.overlay:
                    boxes = state['boxes']
            total_boxes += count
            tile = self.tiles[i]
            if connected:
                online += 1
                self.draw_video(tile, frame, seq, state, boxes, names, count > 0)
            else:
                tile.clear_video()
            if not connected:
                tile.pill.set('OFFLINE', RED)
            elif count:
                tile.pill.set('ERKANNT', ORANGE)
            elif paused:
                tile.pill.set('PAUSIERT', DIM)
            elif not selected:
                tile.pill.set('VORSCHAU', BLUE)
            else:
                tile.pill.set('LIVE', GREEN)
            tile.set_outline(ORANGE if count else (BLUE if mode == i else None))
            if fresh:
                text = (f'{cap_fps:.0f} FPS Kamera · KI {state["fps"]:.1f} FPS · '
                        f'{state["inference"]:.0f} ms · {cam_status}')
            else:
                text = cam_status if not connected else f'{cam_status} · keine aktuelle KI-Auswertung'
            if tile.info.cget('text') != text:
                tile.info.configure(text=text)
            if count and not self.prev_count[i] and t0 - self.last_event[i] > self.args.cooldown:
                self.last_event[i] = t0
                self.events += 1
                saved = self.save_snapshot(i, frame, state, 'erkennung')
                self.log.add(f'{datetime.now():%H:%M:%S}  ·  {camera.name}',
                             f'{count} Objekt(e) · bis {conf:.0%}'
                             + ('  ·  Foto gespeichert' if saved else ''))
            self.prev_count[i] = count

        failed = 'fehler' in status
        if total_boxes:
            title, color = 'Drohne erkannt', ORANGE
        elif not ready:
            title, color = ('Modellfehler', RED) if failed else ('Modell lädt …', DIM)
        elif paused:
            title, color = 'KI pausiert', DIM
        else:
            title, color = 'Überwachung aktiv', GREEN
        self.alert.configure(text=title, fg=color)
        self.dot.set_state(color, (t0 * 1.2) % 1.0)
        if not ready:
            subtitle = status[:60]
        elif t0 < self.notice[1]:
            subtitle = self.notice[0]
        else:
            subtitle = f'{len(self.cameras)} Kamera(s) · {self.args.imgsz} px'
        if self.subtitle.cget('text') != subtitle:
            self.subtitle.configure(text=subtitle)
        if t0 - self.last_sys > 2:
            self.last_sys = t0
            self.read_system()
        if t0 - self.last_sample >= 1:
            self.last_sample = t0
            self.spark.push(total_boxes)
        self.stats['KI FPS'].set(f'{total_fps:.1f}')
        self.stats['Latenz'].set(f'{sum(latencies) / len(latencies):.0f} ms' if latencies else '–')
        self.stats['Kameras'].set(f'{online}/{len(self.cameras)}')
        self.stats['Ereignisse'].set(str(self.events))
        self.stats['CPU Temp'].set(self.sys_text[0])
        self.stats['CPU Last'].set(self.sys_text[1])
        classes = ', '.join(str(v) for v in names.values())[:60] or '–'
        model_text = (f'{self.args.weights.name}\nKlassen: {classes}\n'
                      f'{self.args.device.upper()} · {self.args.threads} Threads · {self.args.imgsz} px')
        if model_text != self.model_text:
            self.model_text = model_text
            self.model_info.configure(text=model_text)
        elapsed = int(t0 - self.started)
        self.clock.configure(text=f'{datetime.now():%d.%m.%Y  ·  %H:%M:%S}   ·   Laufzeit '
                                  f'{elapsed // 3600:02}:{elapsed % 3600 // 60:02}:{elapsed % 60:02}')
        spent = time.perf_counter() - t0
        self.root.after(max(1, int(1000 / self.args.preview_fps - spent * 1000)), self.refresh)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        self.root.destroy()


def pick_font(root):
    global FAMILY
    available = set(tkfont.families(root))
    for name in ('SF Pro Display', 'Inter', 'Segoe UI Variable Display', 'Segoe UI',
                 'Noto Sans', 'DejaVu Sans', 'Helvetica'):
        if name in available:
            FAMILY = name
            return


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--weights', type=Path, default=Path(__file__).resolve().parent / 'best.pt',
                        help='best.pt, .onnx oder NCNN-Ordner (best_ncnn_model)')
    parser.add_argument('--cameras', nargs='+', default=['0', '1', '2'],
                        help='1-3 Quellen: USB-Index (0), Gerätepfad (/dev/video2), '
                             'CSI-Kamera (csi:0) oder URL (rtsp://...)')
    parser.add_argument('--names', nargs='+', default=None,
                        help='Anzeigenamen, z.B. --names "Webcam links" "Webcam rechts" "Detection"')
    parser.add_argument('--imgsz', type=int, choices=[256, 320, 416, 640], default=320)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--threads', type=int, default=4 if platform.machine().startswith('aarch') else
                        max(1, min(4, (os.cpu_count() or 2) // 2)))
    parser.add_argument('--conf', type=float, default=0.25)
    parser.add_argument('--preview-fps', type=int, choices=range(10, 31), default=20, metavar='10-30')
    parser.add_argument('--snapshots', type=Path, default=Path('snapshots'),
                        help='Ordner für Fotos bei Erkennung')
    parser.add_argument('--no-snapshots', action='store_true')
    parser.add_argument('--cooldown', type=float, default=5.0,
                        help='Sekunden Pause zwischen zwei Ereignissen pro Kamera')
    parser.add_argument('--fullscreen', action='store_true')
    args = parser.parse_args()
    if not (args.weights.is_file() or args.weights.is_dir()):
        parser.error(f'Modell fehlt: {args.weights}')
    if not 1 <= len(args.cameras) <= 3:
        parser.error('Bitte 1 bis 3 Kameras angeben.')
    if len(set(args.cameras)) != len(args.cameras):
        parser.error('Kameraquellen müssen unterschiedlich sein.')
    if args.no_snapshots:
        args.snapshots = None
    cv2.setNumThreads(1)
    root = tk.Tk()
    pick_font(root)
    Monitor(root, args)
    if args.fullscreen:
        root.attributes('-fullscreen', True)
    root.mainloop()


if __name__ == '__main__':
    main()