# ui/integrated_timeline.py — Single timeline: seek bar + trim/split markers

import tkinter as tk
from ui.theme import COLORS, FONTS
from core.video_info import seconds_to_str


class IntegratedTimeline(tk.Frame):
    """
    One unified timeline canvas containing:
      • Playhead  (white circle) — seek position
      • IN marker (green ▼)    — trim start
      • OUT marker (red ▼)     — trim end
      • Split marker (amber ◆) — split point

    mode: 'trim' | 'split' | 'compress'
    Callbacks:
      on_seek(s)       — user dragged playhead
      on_in(s)         — IN marker moved
      on_out(s)        — OUT marker moved
      on_split(s)      — split marker moved
    """

    H         = 72   # total canvas height
    TRACK_Y   = 28   # vertical center of main track
    TRACK_H   = 8
    THUMB_R   = 9    # playhead radius
    MARKER_H  = 14   # marker triangle height
    PAD       = 16   # left/right padding

    def __init__(self, parent, on_seek=None, on_in=None, on_out=None, on_split=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)

        self.on_seek  = on_seek
        self.on_in    = on_in
        self.on_out   = on_out
        self.on_split = on_split

        self._duration  = 1.0
        self._mode      = "trim"

        # Normalized positions (0..1)
        self._play_pos  = 0.0
        self._in_pos    = 0.0
        self._out_pos   = 1.0
        self._split_pos = 0.5

        self._drag      = None   # which handle is being dragged

        self._build()

    # ─── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.canvas = tk.Canvas(
            self, height=self.H, bg=COLORS["bg_card"],
            highlightthickness=0, cursor="crosshair",
        )
        self.canvas.pack(fill="x", padx=self.PAD)

        self.canvas.bind("<Configure>",       self._redraw)
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Time labels row
        lbl_row = tk.Frame(self, bg=COLORS["bg_card"])
        lbl_row.pack(fill="x", padx=self.PAD + 4)

        # IN time
        self._in_lbl = tk.Label(lbl_row, text="00:00:00", font=FONTS["small"],
                                 fg=COLORS["in_marker"], bg=COLORS["bg_card"])
        self._in_lbl.pack(side="left")

        # Current / total
        self._cur_lbl = tk.Label(lbl_row, text="00:00:00 / 00:00:00",
                                  font=FONTS["mono"], fg=COLORS["text_secondary"],
                                  bg=COLORS["bg_card"])
        self._cur_lbl.pack(side="left", expand=True)

        # OUT / split time
        self._out_lbl = tk.Label(lbl_row, text="00:00:00", font=FONTS["small"],
                                  fg=COLORS["out_marker"], bg=COLORS["bg_card"])
        self._out_lbl.pack(side="right")

    # ─── Public API ────────────────────────────────────────────────────────────

    def set_duration(self, duration: float):
        self._duration  = max(duration, 0.001)
        self._play_pos  = 0.0
        self._in_pos    = 0.0
        self._out_pos   = 1.0
        self._split_pos = 0.5
        self._redraw()
        self._update_labels()

    def set_mode(self, mode: str):
        self._mode = mode
        self._redraw()
        self._update_labels()

    def set_play_pos(self, s: float):
        """Update playhead position (called by video player every frame)."""
        self._play_pos = s / self._duration if self._duration > 0 else 0.0
        self._play_pos = max(0.0, min(1.0, self._play_pos))
        self._update_playhead_only()
        self._update_labels()

    def get_in_s(self)    -> float: return self._in_pos   * self._duration
    def get_out_s(self)   -> float: return self._out_pos  * self._duration
    def get_split_s(self) -> float: return self._split_pos * self._duration
    def get_play_s(self)  -> float: return self._play_pos  * self._duration

    def set_in_pos(self, s: float):
        self._in_pos = max(0.0, min(s / self._duration, self._out_pos - 0.001))
        self._redraw()
        self._update_labels()

    def set_out_pos(self, s: float):
        self._out_pos = min(1.0, max(s / self._duration, self._in_pos + 0.001))
        self._redraw()
        self._update_labels()

    def set_split_pos(self, s: float):
        self._split_pos = max(0.001, min(s / self._duration, 0.999))
        self._redraw()
        self._update_labels()

    # ─── Drawing ───────────────────────────────────────────────────────────────

    def _x(self, pos: float) -> float:
        """Convert normalized pos to canvas x."""
        w = self.canvas.winfo_width()
        return pos * max(1, w) 

    def _pos(self, x: float) -> float:
        """Convert canvas x to normalized pos."""
        w = self.canvas.winfo_width()
        return max(0.0, min(1.0, x / max(1, w)))

    def _redraw(self, event=None):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 10:
            return
        ty = self.TRACK_Y
        th = self.TRACK_H

        # ── Background track ──
        c.create_rectangle(0, ty - th // 2, w, ty + th // 2,
                           fill=COLORS["timeline_bg"], outline="", width=0, tags="track")

        # ── Mode-specific fills and markers ──
        if self._mode == "trim":
            in_x  = self._x(self._in_pos)
            out_x = self._x(self._out_pos)

            # Gray before IN
            c.create_rectangle(0, ty - th // 2, in_x, ty + th // 2,
                               fill="#D1D5DB", outline="", tags="fill_left")
            # Accent fill IN→OUT
            c.create_rectangle(in_x, ty - th // 2, out_x, ty + th // 2,
                               fill=COLORS["accent"], outline="", tags="fill_sel")
            # Gray after OUT
            c.create_rectangle(out_x, ty - th // 2, w, ty + th // 2,
                               fill="#D1D5DB", outline="", tags="fill_right")

            # IN marker
            self._draw_down_triangle(c, in_x, ty - th // 2,
                                     COLORS["in_marker"], "marker_in")
            # OUT marker
            self._draw_down_triangle(c, out_x, ty - th // 2,
                                     COLORS["out_marker"], "marker_out")

        elif self._mode == "split":
            sp_x = self._x(self._split_pos)

            c.create_rectangle(0, ty - th // 2, sp_x, ty + th // 2,
                               fill=COLORS["accent_light"], outline="", tags="fill_left")
            c.create_rectangle(sp_x, ty - th // 2, w, ty + th // 2,
                               fill=COLORS["timeline_bar"], outline="", tags="fill_right")

            # Split marker (tall line + diamond)
            c.create_line(sp_x, 0, sp_x, ty + th // 2,
                          fill=COLORS["split_marker"], width=2, dash=(4, 3), tags="marker_split")
            self._draw_diamond(c, sp_x, ty - th // 2 - 6,
                               COLORS["split_marker"], "marker_split")

        else:  # compress
            c.create_rectangle(0, ty - th // 2, w, ty + th // 2,
                               fill=COLORS["accent_light"], outline="", tags="fill")

        # ── Playhead ──
        play_x = self._x(self._play_pos)
        # Stem
        c.create_line(play_x, 0, play_x, ty + th // 2 + 4,
                      fill="white", width=2, tags="playhead_line")
        # Circle
        r = self.THUMB_R
        c.create_oval(play_x - r, ty - th // 2 - r,
                      play_x + r, ty - th // 2 + r,
                      fill=COLORS["accent"], outline="white", width=2, tags="playhead")

        # Tick marks every 10% for long videos
        self._draw_ticks(c, w, ty, th)

    def _update_playhead_only(self):
        """Fast path: only move the playhead without full redraw."""
        c = self.canvas
        w = c.winfo_width()
        if w < 10:
            return
        play_x = self._x(self._play_pos)
        ty = self.TRACK_Y
        th = self.TRACK_H
        r  = self.THUMB_R

        c.coords("playhead_line", play_x, 0, play_x, ty + th // 2 + 4)
        c.coords("playhead",
                 play_x - r, ty - th // 2 - r,
                 play_x + r, ty - th // 2 + r)
        c.tag_raise("playhead_line")
        c.tag_raise("playhead")

    def _draw_down_triangle(self, c, x: float, y: float, color: str, tag: str):
        """Draw a downward-pointing triangle marker at (x, y)."""
        h = self.MARKER_H
        hw = 7
        c.create_polygon(
            x - hw, y - h,
            x + hw, y - h,
            x,      y,
            fill=color, outline="white", width=1, tags=tag,
        )

    def _draw_diamond(self, c, x: float, y: float, color: str, tag: str):
        s = 8
        c.create_polygon(
            x,     y - s,
            x + s, y,
            x,     y + s,
            x - s, y,
            fill=color, outline="white", width=1, tags=tag,
        )

    def _draw_ticks(self, c, w: int, ty: int, th: int):
        """Draw subtle time tick marks."""
        if self._duration < 10:
            return
        # Choose tick interval based on duration
        intervals = [1, 5, 10, 30, 60, 300, 600]
        target_ticks = 20
        interval = intervals[-1]
        for iv in intervals:
            if self._duration / iv <= target_ticks:
                interval = iv
                break

        t = interval
        while t < self._duration:
            tx = self._x(t / self._duration)
            c.create_line(tx, ty + th // 2, tx, ty + th // 2 + 5,
                          fill="#9CA3AF", width=1)
            t += interval

    # ─── Drag interaction ──────────────────────────────────────────────────────

    def _on_press(self, event):
        self._drag = self._hit(event.x, event.y)
        if self._drag is None:
            # Click anywhere → seek
            self._drag = "play"
        self._apply_drag(event.x)

    def _on_drag(self, event):
        if self._drag:
            self._apply_drag(event.x)

    def _on_release(self, event):
        self._drag = None

    def _hit(self, x: float, y: float) -> str | None:
        """Return which handle is at (x,y), or None."""
        r = 14  # hit radius

        if self._mode == "trim":
            in_x  = self._x(self._in_pos)
            out_x = self._x(self._out_pos)
            # Check playhead first (it's on top)
            play_x = self._x(self._play_pos)
            if abs(x - play_x) < r:
                return "play"
            if abs(x - in_x) < r:
                return "in"
            if abs(x - out_x) < r:
                return "out"
        elif self._mode == "split":
            sp_x   = self._x(self._split_pos)
            play_x = self._x(self._play_pos)
            if abs(x - play_x) < r:
                return "play"
            if abs(x - sp_x) < r:
                return "split"
        return None

    def _apply_drag(self, x: float):
        pos = self._pos(x)
        if self._drag == "play":
            self._play_pos = pos
            self._update_playhead_only()
            self._update_labels()
            if self.on_seek:
                self.on_seek(self._play_pos * self._duration)

        elif self._drag == "in":
            self._in_pos = max(0.0, min(pos, self._out_pos - 0.01))
            self._redraw()
            self._update_labels()
            if self.on_in:
                self.on_in(self._in_pos * self._duration)

        elif self._drag == "out":
            self._out_pos = min(1.0, max(pos, self._in_pos + 0.01))
            self._redraw()
            self._update_labels()
            if self.on_out:
                self.on_out(self._out_pos * self._duration)

        elif self._drag == "split":
            self._split_pos = max(0.001, min(pos, 0.999))
            self._redraw()
            self._update_labels()
            if self.on_split:
                self.on_split(self._split_pos * self._duration)

    # ─── Labels ────────────────────────────────────────────────────────────────

    def _update_labels(self):
        cur   = seconds_to_str(self._play_pos * self._duration, show_ms=False)
        total = seconds_to_str(self._duration, show_ms=False)
        self._cur_lbl.config(text=f"{cur} / {total}")

        if self._mode == "trim":
            self._in_lbl.config(
                text=f"IN: {seconds_to_str(self._in_pos * self._duration, show_ms=False)}",
                fg=COLORS["in_marker"])
            self._out_lbl.config(
                text=f"OUT: {seconds_to_str(self._out_pos * self._duration, show_ms=False)}",
                fg=COLORS["out_marker"])
        elif self._mode == "split":
            self._in_lbl.config(
                text=f"P1: {seconds_to_str(self._split_pos * self._duration, show_ms=False)}",
                fg=COLORS["split_marker"])
            self._out_lbl.config(
                text=f"P2: {seconds_to_str(self._duration - self._split_pos * self._duration, show_ms=False)}",
                fg=COLORS["split_marker"])
        else:
            self._in_lbl.config(text="", fg=COLORS["bg_card"])
            self._out_lbl.config(text="", fg=COLORS["bg_card"])
