# ui/video_player.py — Embedded video player with playback controls

import tkinter as tk
import time
import threading

try:
    import cv2
    from PIL import Image, ImageTk
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from ui.theme import COLORS, FONTS
from core.video_info import seconds_to_str


class VideoPlayer(tk.Frame):
    """
    Embedded video preview player.
    - Plays video using opencv + PIL
    - Seek bar synced with timeline
    - Buttons: Set IN / Set OUT / Set Split (depends on mode)
    - Calls on_position_change(s) when playback moves
    - Calls on_set_in(s), on_set_out(s), on_set_split(s) when marker buttons clicked
    """

    DISPLAY_FPS = 30   # Max frames per second displayed (cap for performance)
    CANVAS_H    = 210  # Fixed canvas height

    def __init__(self, parent,
                 on_position_change=None,
                 on_set_in=None,
                 on_set_out=None,
                 on_set_split=None,
                 **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)

        self.on_position_change = on_position_change
        self.on_set_in    = on_set_in
        self.on_set_out   = on_set_out
        self.on_set_split = on_set_split

        # Internal state
        self._cap          = None
        self._playing      = False
        self._current_s    = 0.0
        self._duration     = 1.0
        self._fps          = 30.0
        self._after_id     = None
        self._photo        = None
        self._mode         = "trim"     # 'trim' or 'split'
        self._loaded       = False

        # Time-based playback tracking
        self._play_start_wall = 0.0    # wall clock when play began
        self._play_start_pos  = 0.0    # video pos (s) when play began

        # Seek-drag state
        self._seek_dragging = False

        self._build()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Video canvas ──
        self.canvas = tk.Canvas(
            self,
            bg="#1a1a2e",
            height=self.CANVAS_H,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Placeholder
        self._placeholder_id = self.canvas.create_text(
            400, self.CANVAS_H // 2,
            text="🎬  Kéo video vào để xem trước",
            font=FONTS["body"], fill="#6366F1", tags="placeholder",
        )

        # ── Seek bar ──
        seek_frame = tk.Frame(self, bg=COLORS["bg_card"])
        seek_frame.pack(fill="x", padx=10, pady=(4, 0))

        self.seek_canvas = tk.Canvas(
            seek_frame, height=20, bg=COLORS["bg_card"],
            highlightthickness=0, cursor="hand2",
        )
        self.seek_canvas.pack(fill="x")
        self.seek_canvas.bind("<Configure>", self._draw_seek_bar)
        self.seek_canvas.bind("<ButtonPress-1>",   self._on_seek_press)
        self.seek_canvas.bind("<B1-Motion>",       self._on_seek_drag)
        self.seek_canvas.bind("<ButtonRelease-1>", self._on_seek_release)

        self._seek_pct = 0.0  # 0..1

        # ── Controls row ──
        ctrl = tk.Frame(self, bg=COLORS["bg_card"])
        ctrl.pack(fill="x", padx=10, pady=(2, 4))

        # Left: playback controls
        pb = tk.Frame(ctrl, bg=COLORS["bg_card"])
        pb.pack(side="left")

        self.play_btn = tk.Button(
            pb, text="▶", font=("Segoe UI", 14),
            bg=COLORS["accent"], fg="white",
            relief="flat", bd=0, width=3, height=1,
            cursor="hand2", activebackground=COLORS["accent_dark"],
            command=self.toggle_play,
        )
        self.play_btn.pack(side="left", padx=(0, 4))

        tk.Button(
            pb, text="◀◀", font=FONTS["small"],
            bg=COLORS["bg_sidebar"], fg=COLORS["text_primary"],
            relief="flat", bd=0, padx=6, pady=4, cursor="hand2",
            activebackground=COLORS["bg_hover"],
            command=lambda: self.skip(-10),
        ).pack(side="left", padx=(0, 2))

        tk.Button(
            pb, text="▶▶", font=FONTS["small"],
            bg=COLORS["bg_sidebar"], fg=COLORS["text_primary"],
            relief="flat", bd=0, padx=6, pady=4, cursor="hand2",
            activebackground=COLORS["bg_hover"],
            command=lambda: self.skip(10),
        ).pack(side="left", padx=(0, 8))

        # Time label
        self.time_var = tk.StringVar(value="00:00:00 / 00:00:00")
        tk.Label(
            pb, textvariable=self.time_var,
            font=FONTS["mono"], bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
        ).pack(side="left")

        # Right: marker buttons
        mk = tk.Frame(ctrl, bg=COLORS["bg_card"])
        mk.pack(side="right")

        # Trim mode buttons
        self.btn_set_in = tk.Button(
            mk, text="📍 Đặt điểm BĐ",
            font=FONTS["small"], bg=COLORS["success_bg"], fg=COLORS["success"],
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            activebackground="#A7F3D0",
            command=self._do_set_in,
        )
        self.btn_set_out = tk.Button(
            mk, text="📍 Đặt điểm KT",
            font=FONTS["small"], bg=COLORS["danger_bg"], fg=COLORS["danger"],
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            activebackground="#FECACA",
            command=self._do_set_out,
        )
        # Split mode button
        self.btn_set_split = tk.Button(
            mk, text="📍 Đặt điểm cắt tại đây",
            font=FONTS["small"], bg="#FEF3C7", fg=COLORS["warning"],
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            activebackground="#FDE68A",
            command=self._do_set_split,
        )

        self._update_mode_buttons()

    # ─── Public API ────────────────────────────────────────────────────────────

    def load(self, filepath: str, duration: float, fps: float):
        """Load a video file and show the first frame."""
        if not HAS_CV2:
            self._show_placeholder("opencv-python chưa được cài đặt")
            return

        self._stop_playback()
        if self._cap:
            self._cap.release()

        self._cap        = cv2.VideoCapture(filepath)
        self._duration   = max(duration, 0.001)
        self._fps        = fps if fps > 0 else 30.0
        self._current_s  = 0.0
        self._seek_pct   = 0.0
        self._loaded     = True

        self._seek_to_pos(0.0)
        self._update_time_label()
        self._draw_seek_bar()

    def set_mode(self, mode: str):
        """Switch between 'trim' and 'split' marker buttons."""
        self._mode = mode
        self._update_mode_buttons()

    def toggle_play(self):
        if not self._loaded:
            return
        if self._playing:
            self._pause()
        else:
            self._play()

    def skip(self, seconds: float):
        """Skip forward/backward by N seconds."""
        if not self._loaded:
            return
        new_pos = max(0.0, min(self._duration, self._current_s + seconds))
        self._seek_to_pos(new_pos)

    def seek_to(self, seconds: float):
        """Externally seek to a position (e.g. from timeline click)."""
        if not self._loaded:
            return
        self._seek_to_pos(max(0.0, min(self._duration, seconds)))

    def get_current_time(self) -> float:
        return self._current_s

    def destroy(self):
        self._stop_playback()
        if self._cap:
            self._cap.release()
            self._cap = None
        super().destroy()

    # ─── Playback ──────────────────────────────────────────────────────────────

    def _play(self):
        if self._current_s >= self._duration - 0.1:
            self._seek_to_pos(0.0)

        self._play_start_wall = time.time()
        self._play_start_pos  = self._current_s
        self._playing = True
        self.play_btn.configure(text="⏸")
        self._tick()

    def _pause(self):
        self._playing = False
        self.play_btn.configure(text="▶")
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def _stop_playback(self):
        self._pause()

    def _tick(self):
        """Main playback loop — called via after()."""
        if not self._playing or self._cap is None:
            return

        # Calculate target position
        elapsed = time.time() - self._play_start_wall
        target_s = self._play_start_pos + elapsed

        if target_s >= self._duration:
            target_s = self._duration
            self._seek_to_pos(target_s)
            self._pause()
            return

        # Seek cap to target position
        self._cap.set(cv2.CAP_PROP_POS_MSEC, target_s * 1000)
        ret, frame = self._cap.read()
        if ret:
            self._current_s = target_s
            self._seek_pct  = target_s / self._duration
            self._show_frame(frame)
            self._update_time_label()
            self._draw_seek_bar()
            if self.on_position_change:
                try:
                    self.on_position_change(self._current_s)
                except Exception:
                    pass

        # Schedule next tick
        delay = max(16, int(1000 / self.DISPLAY_FPS))  # ~30fps
        self._after_id = self.after(delay, self._tick)

    # ─── Frame display ─────────────────────────────────────────────────────────

    def _seek_to_pos(self, s: float):
        """Seek to position s (seconds) and display that frame."""
        self._current_s = s
        self._seek_pct  = s / self._duration if self._duration > 0 else 0

        if self._cap is None or not HAS_CV2:
            return

        self._cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
        ret, frame = self._cap.read()
        if ret:
            self._show_frame(frame)
        self._update_time_label()
        self._draw_seek_bar()

        if self.on_position_change:
            try:
                self.on_position_change(self._current_s)
            except Exception:
                pass

    def _show_frame(self, frame):
        """Convert cv2 frame to PhotoImage and display on canvas."""
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        # Convert BGR → RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)

        # Scale to fit canvas while keeping aspect ratio
        iw, ih = img.size
        scale = min(cw / iw, ch / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        if nw > 0 and nh > 0:
            img = img.resize((nw, nh), Image.NEAREST)

        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("placeholder")
        self.canvas.delete("frame")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo,
                                  anchor="center", tags="frame")

    def _show_placeholder(self, msg: str = "🎬  Kéo video vào để xem trước"):
        self.canvas.delete("frame")
        self.canvas.delete("placeholder")
        w = self.canvas.winfo_width() or 400
        self._placeholder_id = self.canvas.create_text(
            w // 2, self.CANVAS_H // 2,
            text=msg, font=FONTS["body"],
            fill="#6366F1", tags="placeholder",
        )

    def _on_canvas_resize(self, event):
        # Redraw current frame or placeholder
        if self._loaded and self._cap:
            self._seek_to_pos(self._current_s)
        else:
            self._show_placeholder()

    def _on_canvas_click(self, event):
        """Click on canvas to toggle play/pause."""
        self.toggle_play()

    # ─── Seek bar ──────────────────────────────────────────────────────────────

    def _draw_seek_bar(self, event=None):
        c = self.seek_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 10:
            return
        h = 20
        pad = 6
        bar_y = h // 2
        bar_h = 5

        # Track
        c.create_rectangle(pad, bar_y - bar_h // 2,
                            w - pad, bar_y + bar_h // 2,
                            fill=COLORS["slider_track"], outline="", width=0)

        # Fill
        fill_x = pad + self._seek_pct * (w - 2 * pad)
        if fill_x > pad:
            c.create_rectangle(pad, bar_y - bar_h // 2,
                                fill_x, bar_y + bar_h // 2,
                                fill=COLORS["accent"], outline="", width=0)

        # Handle
        r = 7
        c.create_oval(fill_x - r, bar_y - r, fill_x + r, bar_y + r,
                      fill=COLORS["accent"], outline="white", width=2)

    def _pos_from_seek_x(self, x: float) -> float:
        w = self.seek_canvas.winfo_width()
        pad = 6
        pct = (x - pad) / max(1, w - 2 * pad)
        return max(0.0, min(1.0, pct)) * self._duration

    def _on_seek_press(self, event):
        self._seek_dragging = True
        was_playing = self._playing
        self._pause()
        self._seek_dragging_was_playing = was_playing
        self._seek_to_pos(self._pos_from_seek_x(event.x))

    def _on_seek_drag(self, event):
        if self._seek_dragging:
            self._seek_to_pos(self._pos_from_seek_x(event.x))

    def _on_seek_release(self, event):
        if self._seek_dragging:
            self._seek_to_pos(self._pos_from_seek_x(event.x))
            self._seek_dragging = False
            if getattr(self, "_seek_dragging_was_playing", False):
                self._play()

    # ─── Marker buttons ────────────────────────────────────────────────────────

    def _do_set_in(self):
        if self.on_set_in:
            self.on_set_in(self._current_s)

    def _do_set_out(self):
        if self.on_set_out:
            self.on_set_out(self._current_s)

    def _do_set_split(self):
        if self.on_set_split:
            self.on_set_split(self._current_s)

    def _update_mode_buttons(self):
        """Show trim or split buttons depending on mode."""
        self.btn_set_in.pack_forget()
        self.btn_set_out.pack_forget()
        self.btn_set_split.pack_forget()

        if self._mode == "trim":
            self.btn_set_in.pack(side="right", padx=(0, 4))
            self.btn_set_out.pack(side="right", padx=(0, 4))
        else:
            self.btn_set_split.pack(side="right")

    # ─── Time label ────────────────────────────────────────────────────────────

    def _update_time_label(self):
        cur = seconds_to_str(self._current_s, show_ms=False)
        total = seconds_to_str(self._duration, show_ms=False)
        self.time_var.set(f"{cur} / {total}")
