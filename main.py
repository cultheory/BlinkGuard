import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass

import cv2
from mediapipe import Image, ImageFormat
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions


BLINK_TIMEOUT_SECONDS = 4.0
EAR_THRESHOLD = 0.21
FRAME_SLEEP_SECONDS = 0.01
HOTKEY_ID_QUIT = 1
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_Q = 0x51
WM_HOTKEY = 0x0312

LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)


def get_model_path():
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "models", "face_landmarker.task")


user32 = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", POINT),
        ("lPrivate", ctypes.c_uint),
    ]


def distance(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def calculate_ear(landmarks, indices):
    p1 = landmarks[indices[0]]
    p2 = landmarks[indices[1]]
    p3 = landmarks[indices[2]]
    p4 = landmarks[indices[3]]
    p5 = landmarks[indices[4]]
    p6 = landmarks[indices[5]]
    horizontal = distance(p1, p4)
    if horizontal == 0:
        return 1.0
    return (distance(p2, p6) + distance(p3, p5)) / (2.0 * horizontal)


@dataclass
class WorkerState:
    face_detected: bool = False
    eyes_closed: bool = False
    overlay_requested: bool = False
    last_blink_time: float = 0.0


class BlinkDetectorWorker(threading.Thread):
    def __init__(self, ui_queue, stop_event, blink_timeout_seconds):
        super().__init__(daemon=True)
        self.ui_queue = ui_queue
        self.stop_event = stop_event
        self.blink_timeout_seconds = blink_timeout_seconds

    def post(self, event):
        self.ui_queue.put(event)

    def run(self):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.post(("camera_error", "Camera open failed"))
            return

        state = WorkerState(last_blink_time=time.monotonic())
        self.post(("monitoring_active", "Monitoring"))

        model_path = get_model_path()
        if not os.path.exists(model_path):
            self.post(("camera_error", "Model file missing"))
            cap.release()
            return

        landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=1,
            )
        )

        try:
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    if state.overlay_requested:
                        self.post(("hide_overlay", None))
                        state.overlay_requested = False
                    if state.face_detected:
                        self.post(("face_missing", "Camera read failed"))
                    state.face_detected = False
                    state.eyes_closed = False
                    time.sleep(0.2)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = Image(image_format=ImageFormat.SRGB, data=rgb)
                timestamp_ms = int(time.monotonic() * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if not result.face_landmarks:
                    if state.overlay_requested:
                        self.post(("hide_overlay", None))
                        state.overlay_requested = False
                    if state.face_detected:
                        self.post(("face_missing", "Face not detected"))
                    state.face_detected = False
                    state.eyes_closed = False
                    time.sleep(FRAME_SLEEP_SECONDS)
                    continue

                if not state.face_detected:
                    state.last_blink_time = time.monotonic()
                    self.post(("face_found", "Monitoring"))

                face = result.face_landmarks[0]
                coords = [(lm.x, lm.y) for lm in face]
                ear = (calculate_ear(coords, LEFT_EYE) + calculate_ear(coords, RIGHT_EYE)) / 2.0
                now = time.monotonic()

                is_closed = ear < EAR_THRESHOLD
                if is_closed and not state.eyes_closed:
                    state.last_blink_time = now
                    if state.overlay_requested:
                        self.post(("hide_overlay", None))
                        state.overlay_requested = False
                    self.post(("blink", "Blink detected"))
                state.eyes_closed = is_closed
                state.face_detected = True

                if not state.overlay_requested and (now - state.last_blink_time) >= self.blink_timeout_seconds:
                    self.post(("show_overlay", None))
                    state.overlay_requested = True

                time.sleep(FRAME_SLEEP_SECONDS)
        finally:
            landmarker.close()
            cap.release()


class BlinkGuardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BlinkGuard")
        self.root.resizable(False, False)
        self.root.geometry("220x100")
        self.root.protocol("WM_DELETE_WINDOW", self.force_quit)

        self.monitoring = False
        self.overlay_active = False
        self.paused = True
        self.status_var = tk.StringVar(value="Stopped")
        self.timeout_var = tk.StringVar(value=str(int(BLINK_TIMEOUT_SECONDS)))
        self.ui_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.hotkey_registered = False

        self.build_main_window()
        self.build_overlay()
        self.register_hotkeys()
        self.root.bind_all("<Escape>", self.on_escape)
        self.root.after(50, self.process_ui_queue)
        self.root.after(50, self.process_hotkeys)

    def build_main_window(self):
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        button_row = tk.Frame(frame)
        button_row.pack(fill="x")

        self.start_button = tk.Button(button_row, text="Start", width=10, command=self.start_monitoring)
        self.start_button.pack(side="left")

        self.stop_button = tk.Button(button_row, text="Stop", width=10, command=self.stop_monitoring, state="disabled")
        self.stop_button.pack(side="right")

        timeout_row = tk.Frame(frame)
        timeout_row.pack(fill="x", pady=(10, 0))

        timeout_label = tk.Label(timeout_row, text="눈 깜박임 없음 시간(초)", anchor="w")
        timeout_label.pack(fill="x")

        timeout_entry = tk.Entry(timeout_row, textvariable=self.timeout_var)
        timeout_entry.pack(fill="x", pady=(4, 0))

        status_label = tk.Label(frame, textvariable=self.status_var, anchor="w")
        status_label.pack(fill="x", pady=(8, 0))

    def build_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg="black")
        self.overlay.attributes("-topmost", True)
        self.overlay.bind("<Escape>", self.on_escape)

    def register_hotkeys(self):
        self.hotkey_registered = bool(
            user32.RegisterHotKey(None, HOTKEY_ID_QUIT, MOD_CONTROL | MOD_ALT, VK_Q)
        )

    def read_timeout_seconds(self):
        raw_value = self.timeout_var.get().strip()
        try:
            timeout_seconds = int(raw_value)
        except ValueError:
            return None
        if timeout_seconds < 1 or timeout_seconds > 60:
            return None
        return timeout_seconds

    def unregister_hotkeys(self):
        if self.hotkey_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_QUIT)
            self.hotkey_registered = False

    def start_monitoring(self):
        if self.monitoring:
            return
        timeout_seconds = self.read_timeout_seconds()
        if timeout_seconds is None:
            messagebox.showerror("BlinkGuard", "blink 없음 시간은 1~60초 정수만 허용됩니다.")
            self.status_var.set("Invalid timeout")
            return
        self.monitoring = True
        self.paused = False
        self.stop_event = threading.Event()
        self.worker = BlinkDetectorWorker(self.ui_queue, self.stop_event, timeout_seconds)
        self.worker.start()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set(f"Starting... ({timeout_seconds}s)")

    def stop_monitoring(self):
        if not self.monitoring:
            return
        self.monitoring = False
        self.paused = True
        self.stop_event.set()
        self.hide_overlay()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("Stopped")

    def show_overlay(self):
        if self.overlay_active or not self.monitoring or self.paused:
            return
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        self.overlay.geometry(f"{width}x{height}+0+0")
        self.overlay.deiconify()
        self.overlay.lift()
        self.overlay.attributes("-topmost", True)
        self.overlay.focus_force()
        self.overlay.grab_set()
        self.overlay_active = True

    def hide_overlay(self):
        if self.overlay_active:
            try:
                self.overlay.grab_release()
            except tk.TclError:
                pass
            self.overlay.withdraw()
            self.overlay_active = False

    def force_quit(self):
        self.stop_monitoring()
        self.unregister_hotkeys()
        self.root.quit()
        self.root.destroy()

    def on_escape(self, _event=None):
        self.hide_overlay()

    def process_ui_queue(self):
        while True:
            try:
                event, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if event == "show_overlay":
                self.show_overlay()
            elif event == "hide_overlay":
                self.hide_overlay()
            elif event == "blink":
                self.paused = False
                self.status_var.set(payload)
                self.hide_overlay()
            elif event == "face_found":
                self.paused = False
                self.status_var.set(payload)
            elif event == "face_missing":
                self.paused = True
                self.status_var.set(payload)
                self.hide_overlay()
            elif event == "camera_error":
                self.paused = True
                self.status_var.set(payload)
                self.hide_overlay()
            elif event == "monitoring_active":
                self.status_var.set(payload)

        self.root.after(50, self.process_ui_queue)

    def process_hotkeys(self):
        msg = MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_QUIT:
                self.force_quit()
                return
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self.root.after(50, self.process_hotkeys)


def main():
    root = tk.Tk()
    app = BlinkGuardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
