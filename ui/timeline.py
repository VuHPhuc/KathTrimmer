# ui/timeline.py — Interactive timeline slider for trim / split

import tkinter as tk
from ui.theme import COLORS, FONTS
from core.video_info import seconds_to_str, str_to_seconds


class TimelineWidget(tk.Frame):
    """
    Visual timeline with draggable IN / OUT / SPLIT markers.
    mode: 'trim' or 'split'
    """

    BAR_H = 36
    MARKER_W = 12
    HANDLE_R = 8
    PAD = 20

    def __init__(self, parent, duration: float = 0, mode: str = "trim", on_change=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        self.duration = duration
        self.mode = mode
        self.on_change = on_change  # callback(in_s, out_s) or callback(split_s)

        # State (normalized 0..1)
        self._in_pos = 0.0
        self._out_pos = 1.0
        self._split_pos = 0.5
        self._dragging = None  # 'in' / 'out' / 'split'

        self._build()

    def _build(self):
        self.canvas = tk.Canvas(
            self,
            height=self.BAR_H + 40,
            bg=COLORS["bg_card"],
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="x", padx=self.PAD, pady=(8, 4))
        self.canvas.bind("<Configure>", self._redraw)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Time labels row
        label_frame = tk.Frame(self, bg=COLORS["bg_card"])
        label_frame.pack(fill="x", padx=self.PAD)

        if self.mode == "trim":
            self._build_trim_labels(label_frame)
        else:
            self._build_split_labels(label_frame)

    def _build_trim_labels(self, frame):
        tk.Label(frame, text="✂ Bắt đầu:", font=FONTS["label"],
                 bg=COLORS["bg_card"], fg=COLORS["in_marker"]).grid(row=0, column=0, sticky="w")
        self.in_entry = tk.Entry(frame, width=12, font=FONTS["mono"],
                                  fg=COLORS["in_marker"], relief="flat",
                                  bg=COLORS["bg_sidebar"], bd=0, insertbackground=COLORS["accent"])
        self.in_entry.grid(row=0, column=1, padx=(4, 20))
        self.in_entry.bind("<Return>", self._on_in_entry)
        self.in_entry.bind("<FocusOut>", self._on_in_entry)

        tk.Label(frame, text="✂ Kết thúc:", font=FONTS["label"],
                 bg=COLORS["bg_card"], fg=COLORS["out_marker"]).grid(row=0, column=2, sticky="w")
        self.out_entry = tk.Entry(frame, width=12, font=FONTS["mono"],
                                   fg=COLORS["out_marker"], relief="flat",
                                   bg=COLORS["bg_sidebar"], bd=0, insertbackground=COLORS["accent"])
        self.out_entry.grid(row=0, column=3, padx=(4, 0))
        self.out_entry.bind("<Return>", self._on_out_entry)
        self.out_entry.bind("<FocusOut>", self._on_out_entry)

        # Duration label
        self.dur_label = tk.Label(frame, text="", font=FONTS["small"],
                                   bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        self.dur_label.grid(row=0, column=4, padx=(20, 0), sticky="e")
        frame.columnconfigure(4, weight=1)

        self._update_entries()

    def _build_split_labels(self, frame):
        tk.Label(frame, text="✂ Điểm cắt:", font=FONTS["label"],
                 bg=COLORS["bg_card"], fg=COLORS["split_marker"]).grid(row=0, column=0, sticky="w")
        self.split_entry = tk.Entry(frame, width=12, font=FONTS["mono"],
                                     fg=COLORS["split_marker"], relief="flat",
                                     bg=COLORS["bg_sidebar"], bd=0, insertbackground=COLORS["accent"])
        self.split_entry.grid(row=0, column=1, padx=(4, 20))
        self.split_entry.bind("<Return>", self._on_split_entry)
        self.split_entry.bind("<FocusOut>", self._on_split_entry)

        self.dur_label = tk.Label(frame, text="", font=FONTS["small"],
                                   bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        self.dur_label.grid(row=0, column=2, padx=(20, 0), sticky="e")
        frame.columnconfigure(2, weight=1)

        self._update_entries()

    def set_duration(self, duration: float):
        self.duration = duration
        self._in_pos = 0.0
        self._out_pos = 1.0
        self._split_pos = 0.5
        self._update_entries()
        self._redraw()

    def set_mode(self, mode: str):
        self.mode = mode
        self._redraw()

    def get_trim_values(self):
        """Returns (in_s, out_s)"""
        return self._in_pos * self.duration, self._out_pos * self.duration

    def get_split_value(self):
        """Returns split_s"""
        return self._split_pos * self.duration

    def _bar_x(self, pos: float) -> float:
        """Convert normalized pos to canvas x."""
        w = self.canvas.winfo_width()
        return pos * (w - 2 * self.PAD) + self.PAD

    def _pos_from_x(self, x: float) -> float:
        """Convert canvas x to normalized pos."""
        w = self.canvas.winfo_width()
        pos = (x - self.PAD) / max(1, w - 2 * self.PAD)
        return max(0.0, min(1.0, pos))

    def _redraw(self, event=None):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 10:
            return
        y_center = self.BAR_H // 2 + 8

        # Background track
        c.create_rectangle(
            self.PAD, y_center - 6, w - self.PAD, y_center + 6,
            fill=COLORS["timeline_bg"], outline=COLORS["border"], width=1
        )

        if self.mode == "trim":
            in_x = self._bar_x(self._in_pos)
            out_x = self._bar_x(self._out_pos)

            # Selection fill
            c.create_rectangle(
                in_x, y_center - 6, out_x, y_center + 6,
                fill=COLORS["accent_bg"], outline="", width=0
            )
            # Selection bar
            c.create_rectangle(
                in_x, y_center - 3, out_x, y_center + 3,
                fill=COLORS["timeline_sel"], outline="", width=0
            )

            # IN marker (green)
            self._draw_handle(c, in_x, y_center, COLORS["in_marker"], "in", "▶")
            # OUT marker (red)
            self._draw_handle(c, out_x, y_center, COLORS["out_marker"], "out", "◀")

            # Time labels on markers
            c.create_text(in_x, y_center + 18, text=seconds_to_str(self._in_pos * self.duration, False),
                          font=FONTS["small"], fill=COLORS["in_marker"], tags="lbl_in")
            c.create_text(out_x, y_center + 18, text=seconds_to_str(self._out_pos * self.duration, False),
                          font=FONTS["small"], fill=COLORS["out_marker"], tags="lbl_out")

        else:  # split
            split_x = self._bar_x(self._split_pos)

            # Left fill
            c.create_rectangle(
                self.PAD, y_center - 3, split_x, y_center + 3,
                fill=COLORS["accent_light"], outline="", width=0
            )
            # Right fill
            c.create_rectangle(
                split_x, y_center - 3, w - self.PAD, y_center + 3,
                fill=COLORS["timeline_bar"], outline="", width=0
            )

            # Split marker (amber)
            self._draw_handle(c, split_x, y_center, COLORS["split_marker"], "split", "⬥")

            c.create_text(split_x, y_center + 18, text=seconds_to_str(self._split_pos * self.duration, False),
                          font=FONTS["small"], fill=COLORS["split_marker"])

            # Part labels
            if split_x > self.PAD + 30:
                c.create_text((self.PAD + split_x) / 2, y_center,
                              text="Phần 1", font=FONTS["small"], fill=COLORS["text_on_accent"])
            if split_x < w - self.PAD - 30:
                c.create_text((split_x + w - self.PAD) / 2, y_center,
                              text="Phần 2", font=FONTS["small"], fill=COLORS["text_on_accent"])

        self._update_entries()

    def _draw_handle(self, c, x, y, color, tag, symbol):
        r = self.HANDLE_R
        c.create_oval(x - r, y - r, x + r, y + r,
                      fill=color, outline="white", width=2, tags=tag)
        c.create_text(x, y, text=symbol, fill="white", font=("Segoe UI", 7, "bold"), tags=tag)

    def _on_press(self, event):
        self._dragging = self._hit_test(event.x, event.y)

    def _on_drag(self, event):
        if self._dragging is None:
            return
        pos = self._pos_from_x(event.x)
        if self._dragging == "in":
            self._in_pos = max(0.0, min(pos, self._out_pos - 0.001))
        elif self._dragging == "out":
            self._out_pos = min(1.0, max(pos, self._in_pos + 0.001))
        elif self._dragging == "split":
            self._split_pos = pos
        self._redraw()
        self._fire_change()

    def _on_release(self, event):
        self._dragging = None

    def _hit_test(self, x, y):
        """Return which marker is closest to x,y, or None."""
        r = self.HANDLE_R + 4
        y_center = self.BAR_H // 2 + 8

        if self.mode == "trim":
            in_x = self._bar_x(self._in_pos)
            out_x = self._bar_x(self._out_pos)
            dist_in = abs(x - in_x)
            dist_out = abs(x - out_x)
            if dist_in < r and dist_in <= dist_out:
                return "in"
            if dist_out < r:
                return "out"
        else:
            split_x = self._bar_x(self._split_pos)
            if abs(x - split_x) < r + 4:
                return "split"

        # Click anywhere on the bar to seek closest
        if abs(y - y_center) < 14:
            if self.mode == "split":
                self._split_pos = self._pos_from_x(x)
                self._redraw()
                self._fire_change()
                return None
        return None

    def _fire_change(self):
        if self.on_change is None:
            return
        if self.mode == "trim":
            self.on_change(self._in_pos * self.duration, self._out_pos * self.duration)
        else:
            self.on_change(self._split_pos * self.duration)

    def _update_entries(self):
        if self.mode == "trim":
            try:
                self.in_entry.delete(0, "end")
                self.in_entry.insert(0, seconds_to_str(self._in_pos * self.duration))
                self.out_entry.delete(0, "end")
                self.out_entry.insert(0, seconds_to_str(self._out_pos * self.duration))
                dur = (self._out_pos - self._in_pos) * self.duration
                try:
                    self.dur_label.config(text=f"Độ dài: {seconds_to_str(dur, False)}")
                except Exception:
                    pass
            except AttributeError:
                pass
        else:
            try:
                self.split_entry.delete(0, "end")
                self.split_entry.insert(0, seconds_to_str(self._split_pos * self.duration))
                s = self._split_pos * self.duration
                try:
                    self.dur_label.config(text=f"P1: {seconds_to_str(s, False)}  |  P2: {seconds_to_str(self.duration - s, False)}")
                except Exception:
                    pass
            except AttributeError:
                pass

    def _on_in_entry(self, event=None):
        try:
            s = str_to_seconds(self.in_entry.get())
            self._in_pos = max(0.0, min(s / self.duration, self._out_pos - 0.001)) if self.duration > 0 else 0.0
            self._redraw()
            self._fire_change()
        except Exception:
            pass

    def _on_out_entry(self, event=None):
        try:
            s = str_to_seconds(self.out_entry.get())
            self._out_pos = min(1.0, max(s / self.duration, self._in_pos + 0.001)) if self.duration > 0 else 1.0
            self._redraw()
            self._fire_change()
        except Exception:
            pass

    def _on_split_entry(self, event=None):
        try:
            s = str_to_seconds(self.split_entry.get())
            self._split_pos = max(0.001, min(s / self.duration, 0.999)) if self.duration > 0 else 0.5
            self._redraw()
            self._fire_change()
        except Exception:
            pass
