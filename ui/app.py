# ui/app.py — KathTrimmer: VLC-first smooth video preview

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import time

from ui.theme import COLORS, FONTS
from ui.drop_zone import DropZone
from ui.integrated_timeline import IntegratedTimeline
from ui.vlc_player import VLCPlayer, vlc_available
from core.video_info import get_video_info, seconds_to_str
from core.ffmpeg_runner import trim_video, split_video, compress_video

# OpenCV fallback
try:
    from PIL import Image, ImageTk
    import cv2
    from ui.threaded_reader import ThreadedReader
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class KathTrimmerApp:
    CURRENT_VERSION = "1.0.0"

    """
    Video-centric layout — VLC preview takes centre stage.

    Playback engine priority:
      1. VLC (hardware-accelerated, perfect quality) — if VLC is installed
      2. OpenCV + PIL (software, ~30fps cap)         — fallback

    Layout:
      [Header]
      [VIDEO FRAME — fills available space]
      [Playback controls bar]
      [Integrated timeline: seek + trim/split markers]
      [Mode tabs: Trim | Split | Compress]
      [Mode action panel (2 rows)]
      [Status bar]
    """

    DISPLAY_POLL_MS = 22   # OpenCV fallback: poll interval

    def __init__(self, root: tk.Tk):
        self.root         = root
        self.video_info   = None
        self.video_path   = None
        self.current_proc = None
        self._photo       = None

        # Playback engine (one of these will be used)
        self.vlc: VLCPlayer | None    = None   # VLC instance
        self.reader: "ThreadedReader | None" = None  # OpenCV fallback

        self._playing = False
        self._after_id = None
        self._cv_image_item = None    # pre-created canvas item (OpenCV path)

        self.mode_var         = tk.StringVar(value="trim")
        self.compress_quality = tk.StringVar(value="balanced")
        self.compress_codec   = tk.StringVar(value="h264")

        self._use_vlc = vlc_available()

        self._setup_window()
        self._build_ui()

        # Start OpenCV display loop (no-op when VLC is in use)
        self._display_loop()

        # Check for updates in a background thread
        import threading
        threading.Thread(target=self._check_update_thread, daemon=True).start()

    # ─── Window ────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("KathTrimmer — Video Cutter")
        self.root.geometry("1060x720")
        self.root.minsize(820, 560)
        self.root.configure(bg=COLORS["bg_main"])
        try:
            ico = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico")
            if os.path.isfile(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass
        self.root.bind("<space>",  lambda e: self._toggle_play())
        self.root.bind("<Left>",   lambda e: self._skip(-5))
        self.root.bind("<Right>",  lambda e: self._skip(5))
        self.root.bind("<Left>",   lambda e: self._skip(-5))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._cleanup()
        self.root.destroy()

    # ─── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_video_area()
        self._build_playback_bar()
        self._build_timeline()
        self._build_mode_tabs()
        self._build_mode_panels()
        self._build_statusbar()
        self._switch_mode("trim")

    # ── Header ──
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=COLORS["accent"], height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🎬  KathTrimmer",
                 font=FONTS["title"], fg="white", bg=COLORS["accent"]).pack(side="left", padx=18)

        engine_lbl = "⚡ VLC" if self._use_vlc else "🐍 OpenCV"
        engine_color = "#A5F3A0" if self._use_vlc else "#FCD34D"
        tk.Label(hdr, text=engine_lbl, font=FONTS["small"],
                 fg=engine_color, bg=COLORS["accent"]).pack(side="left", padx=(0, 8))

        tk.Label(hdr, text="Video Cutter & Compressor",
                 font=FONTS["label"], fg="#A5B4FC", bg=COLORS["accent"]).pack(side="left")

        tk.Button(hdr, text="📂  Mở video",
                  font=FONTS["label"], bg="#3730A3", fg="white",
                  relief="flat", bd=0, padx=14, cursor="hand2",
                  activebackground="#2e27a0",
                  command=self._browse_file).pack(side="right", padx=12, pady=6)

    # ── Video area ──
    def _build_video_area(self):
        self.video_outer = tk.Frame(self.root, bg="#0F0F1A")
        self.video_outer.pack(fill="both", expand=True)

        # Inner frame — VLC or OpenCV renders here
        self.video_frame = tk.Frame(self.video_outer, bg="#0F0F1A")
        self.video_frame.pack(fill="both", expand=True)

        if self._use_vlc:
            # VLC renders directly into this Frame via HWND
            # We put a thin canvas on top only for cursor + click handling
            self.video_canvas = tk.Canvas(
                self.video_frame, bg="#0F0F1A",
                highlightthickness=0, cursor="hand2",
            )
            self.video_canvas.pack(fill="both", expand=True)
            self.video_canvas.bind("<Button-1>",  self._on_canvas_click)
            self.video_canvas.bind("<Configure>", self._on_canvas_resize)
        else:
            # OpenCV renders frames to this canvas
            self.video_canvas = tk.Canvas(
                self.video_frame, bg="#0F0F1A",
                highlightthickness=0, cursor="hand2",
            )
            self.video_canvas.pack(fill="both", expand=True)
            self.video_canvas.bind("<Button-1>",  self._on_canvas_click)
            self.video_canvas.bind("<Configure>", self._on_canvas_resize)
            # Pre-create image item for fast updates
            self._cv_image_item = self.video_canvas.create_image(0, 0, anchor="center")

        # Drop zone overlay (visible until a video is loaded)
        self.drop_zone = DropZone(
            self.video_frame,
            on_file_dropped=self._on_file_loaded,
            bg="#0F0F1A",
        )
        self._show_drop_overlay()

    def _show_drop_overlay(self):
        cw = self.video_frame.winfo_width()  or 900
        ch = self.video_frame.winfo_height() or 400
        self.drop_zone.place(x=0, y=0, width=cw, height=ch)
        self.drop_zone.lift()

    def _hide_drop_overlay(self):
        self.drop_zone.place_forget()

    def _on_canvas_resize(self, event):
        if self.video_info is None:
            self.drop_zone.place(x=0, y=0,
                                  width=event.width, height=event.height)
        if self.reader:
            self.reader.resize_canvas(event.width, event.height)
        # Re-centre the pre-created image item
        if self._cv_image_item:
            self.video_canvas.coords(self._cv_image_item,
                                      event.width // 2, event.height // 2)

    def _on_canvas_click(self, event):
        if self.video_info:
            self._toggle_play()

    # ── Playback controls bar ──
    def _build_playback_bar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_card"], height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=COLORS["bg_card"])
        left.pack(side="left", padx=12, fill="y")

        def _btn(parent, text, cmd, w=None, big=False):
            kw = dict(font=(("Segoe UI", 14) if big else FONTS["small"]),
                      bg=(COLORS["accent"] if big else COLORS["bg_sidebar"]),
                      fg="white" if big else COLORS["text_primary"],
                      relief="flat", bd=0, padx=(3 if big else 8), pady=4,
                      cursor="hand2",
                      activebackground=(COLORS["accent_dark"] if big else COLORS["bg_hover"]),
                      command=cmd)
            if w:
                kw["width"] = w
            return tk.Button(parent, text=text, **kw)

        _btn(left, "⏮ 10s", lambda: self._skip(-10)).pack(side="left", padx=(0, 4))

        self.play_btn = _btn(left, "▶", self._toggle_play, w=3, big=True)
        self.play_btn.pack(side="left", padx=(0, 4))

        _btn(left, "10s ⏭", lambda: self._skip(10)).pack(side="left", padx=(0, 12))

        tk.Label(left, text="Space = play/pause  •  ← → = ±5s",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(side="left")

        # Video meta on the right
        self.info_var = tk.StringVar(value="Chưa có video")
        tk.Label(bar, textvariable=self.info_var,
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"]).pack(side="right", padx=14)

    # ── Integrated timeline ──
    def _build_timeline(self):
        wrap = tk.Frame(self.root, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        wrap.pack(fill="x")
        self.timeline = IntegratedTimeline(
            wrap,
            on_seek=self._on_tl_seek,
            on_in=None, on_out=None, on_split=None,
        )
        self.timeline.pack(fill="x", padx=8, pady=4)

    # ── Mode tabs ──
    def _build_mode_tabs(self):
        tab_bar = tk.Frame(self.root, bg=COLORS["bg_sidebar"])
        tab_bar.pack(fill="x")
        self.tab_btns = {}
        for key, label in [("trim", "✂  Cắt đoạn (Trim)"),
                            ("split", "⚡  Tách đôi (Split)"),
                            ("compress", "📦  Nén video (Compress)")]:
            b = tk.Button(tab_bar, text=label, font=FONTS["label"],
                          relief="flat", bd=0, padx=20, pady=9, cursor="hand2",
                          bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                          activebackground=COLORS["bg_hover"],
                          command=lambda k=key: self._switch_mode(k))
            b.pack(side="left")
            self.tab_btns[key] = b

    def _switch_mode(self, mode: str):
        self.mode_var.set(mode)
        for k, b in self.tab_btns.items():
            b.configure(
                bg=COLORS["bg_card"]    if k == mode else COLORS["bg_sidebar"],
                fg=COLORS["accent"]     if k == mode else COLORS["text_secondary"],
                font=FONTS["subhead"]   if k == mode else FONTS["label"],
            )
        self.timeline.set_mode(mode)
        for f in (self.trim_panel, self.split_panel, self.compress_panel):
            f.pack_forget()
        {"trim": self.trim_panel,
         "split": self.split_panel,
         "compress": self.compress_panel}[mode].pack(fill="x")

    # ── Mode panels ──
    def _build_mode_panels(self):
        self._build_trim_panel()
        self._build_split_panel()
        self._build_compress_panel()

    def _build_trim_panel(self):
        self.trim_panel = tk.Frame(self.root, bg=COLORS["bg_card"],
                                   highlightbackground=COLORS["border"], highlightthickness=1)
        # Row 1
        r1 = tk.Frame(self.trim_panel, bg=COLORS["bg_card"])
        r1.pack(fill="x", padx=14, pady=(8, 2))
        tk.Label(r1, text="✂  Kéo marker xanh/đỏ trên timeline, hoặc phát video rồi nhấn:",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], anchor="w").pack(side="left")
        tk.Button(r1, text="📍 Đặt điểm KT", font=FONTS["small"],
                  bg=COLORS["danger_bg"], fg=COLORS["danger"],
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._set_out_here).pack(side="right", padx=(4, 0))
        tk.Button(r1, text="📍 Đặt điểm BĐ", font=FONTS["small"],
                  bg=COLORS["success_bg"], fg=COLORS["success"],
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._set_in_here).pack(side="right", padx=(0, 6))
        # Row 2: output + export
        self._build_export_row(self.trim_panel, "trim")

    def _build_split_panel(self):
        self.split_panel = tk.Frame(self.root, bg=COLORS["bg_card"],
                                    highlightbackground=COLORS["border"], highlightthickness=1)
        r1 = tk.Frame(self.split_panel, bg=COLORS["bg_card"])
        r1.pack(fill="x", padx=14, pady=(8, 2))
        tk.Label(r1, text="⚡  Kéo marker vàng trên timeline, hoặc phát video rồi nhấn:",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], anchor="w").pack(side="left")
        tk.Button(r1, text="📍 Đặt điểm cắt tại đây", font=FONTS["small"],
                  bg="#FEF3C7", fg=COLORS["warning"],
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._set_split_here).pack(side="right")
        self._build_export_row(self.split_panel, "split")

    def _build_compress_panel(self):
        self.compress_panel = tk.Frame(self.root, bg=COLORS["bg_card"],
                                       highlightbackground=COLORS["border"], highlightthickness=1)
        r1 = tk.Frame(self.compress_panel, bg=COLORS["bg_card"])
        r1.pack(fill="x", padx=14, pady=(8, 2))
        tk.Label(r1, text="Codec:", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="left")
        for v, l in [("h264", "H.264 (MP4)"), ("h265", "H.265 – nhỏ hơn ~40%")]:
            tk.Radiobutton(r1, text=l, variable=self.compress_codec, value=v,
                           font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                           activebackground=COLORS["bg_card"], selectcolor=COLORS["accent_bg"],
                           relief="flat", cursor="hand2").pack(side="left", padx=(6, 12))
        tk.Label(r1, text="Chất lượng:", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="left")
        for v, l in [("light", "Nhẹ CRF18"), ("balanced", "Cân bằng CRF23 ✓"), ("strong", "Mạnh CRF28")]:
            tk.Radiobutton(r1, text=l, variable=self.compress_quality, value=v,
                           font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                           activebackground=COLORS["bg_card"], selectcolor=COLORS["accent_bg"],
                           relief="flat", cursor="hand2").pack(side="left", padx=(4, 8))
        self._build_export_row(self.compress_panel, "compress")
        
        # Warning label for compressed video (hidden by default)
        self.compress_warning = tk.Label(
            self.compress_panel,
            text="⚠️ Video này dường như đã được nén tối ưu từ trước. Nén tiếp có thể làm giảm chất lượng hình ảnh và không giảm thêm được dung lượng (MB) nào!",
            font=FONTS["small"], bg=COLORS["danger_bg"], fg=COLORS["danger"],
            anchor="w", justify="left", padx=8, pady=4
        )

    def _build_export_row(self, frame, mode_key):
        r2 = tk.Frame(frame, bg=COLORS["bg_card"])
        r2.pack(fill="x", padx=14, pady=(2, 8))
        setattr(self, f"export_row_{mode_key}", r2)

        tk.Label(r2, text="📂 Lưu vào:", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="left")

        entry = tk.Entry(r2, font=FONTS["small"], relief="flat", bd=0,
                         bg=COLORS["bg_sidebar"], fg=COLORS["text_primary"],
                         insertbackground=COLORS["accent"])
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(6, 4))
        setattr(self, f"out_entry_{mode_key}", entry)

        tk.Button(r2, text="...", font=FONTS["small"],
                  bg=COLORS["bg_sidebar"], fg=COLORS["accent"],
                  relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
                  command=lambda: self._browse_output(entry)).pack(side="left", padx=(0, 12))

        lbl = "▶  Xuất video" if mode_key != "compress" else "📦  Nén & Xuất"
        btn = tk.Button(r2, text=lbl, font=FONTS["btn"],
                        bg=COLORS["accent"], fg="white",
                        relief="flat", bd=0, padx=22, pady=6, cursor="hand2",
                        activebackground=COLORS["accent_dark"],
                        command=lambda: self._export(mode_key))
        btn.pack(side="left")
        setattr(self, f"export_btn_{mode_key}", btn)

        can_btn = tk.Button(r2, text="✕ Hủy", font=FONTS["small"],
                            bg=COLORS["danger_bg"], fg=COLORS["danger"],
                            relief="flat", bd=0, padx=10, pady=6, cursor="hand2",
                            command=self._cancel)
        can_btn.pack(side="left", padx=(8, 0))
        can_btn.pack_forget()
        setattr(self, f"cancel_btn_{mode_key}", can_btn)

    # ── Status bar ──
    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_sidebar"], height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_var = tk.StringVar(value="Sẵn sàng — kéo thả hoặc nhấn 📂 Mở video")
        tk.Label(bar, textvariable=self.status_var,
                 font=FONTS["small"], bg=COLORS["bg_sidebar"],
                 fg=COLORS["text_secondary"], anchor="w").pack(side="left", padx=10, fill="y")

        self.prog_canvas = tk.Canvas(bar, width=160, height=6,
                                      bg=COLORS["slider_track"], highlightthickness=0)
        self.prog_canvas.pack(side="right", padx=10, pady=11)
        self._prog_bar = self.prog_canvas.create_rectangle(
            0, 0, 0, 6, fill=COLORS["accent"], outline="")

    # ─── OpenCV display loop (no-op when VLC active) ──────────────────────────

    def _display_loop(self):
        if self.reader and self._playing:
            last_pos = None
            for _ in range(3):   # drain up to 3 frames per tick
                res = self.reader.get_frame()
                if res is None:
                    break
                frame_rgb, pos_s = res
                last_pos = pos_s
                self._show_cv_frame(frame_rgb)
            if last_pos is not None:
                self.timeline.set_play_pos(last_pos)
                if last_pos >= self.video_info["duration_s"] - 0.2:
                    self._set_playing(False)

        self._after_id = self.root.after(self.DISPLAY_POLL_MS, self._display_loop)

    def _show_cv_frame(self, frame_rgb):
        """Display a pre-resized RGB numpy array on the canvas (fast path)."""
        try:
            img = Image.fromarray(frame_rgb)
            self._photo = ImageTk.PhotoImage(img)
            self.video_canvas.itemconfig(self._cv_image_item, image=self._photo)
        except Exception:
            pass

    # ─── Playback controls ─────────────────────────────────────────────────────

    def _toggle_play(self):
        if not self.video_info:
            return
        self._set_playing(not self._playing)

    def _set_playing(self, playing: bool):
        self._playing = playing
        self.play_btn.configure(text="⏸" if playing else "▶")

        if self._use_vlc and self.vlc:
            if playing:
                self.vlc.play()
            else:
                self.vlc.pause()
        elif self.reader:
            if playing:
                self.reader.play()
            else:
                self.reader.pause()

    def _skip(self, seconds: float):
        if not self.video_info:
            return
        dur = self.video_info["duration_s"]
        was_playing = self._playing

        if self._use_vlc and self.vlc:
            cur = self.vlc.get_time()
            new_pos = max(0.0, min(dur, cur + seconds))
            self.vlc.seek(new_pos)
            self.timeline.set_play_pos(new_pos)
        else:
            cur = self.timeline.get_play_s()
            new_pos = max(0.0, min(dur, cur + seconds))
            self._seek_to_cv(new_pos)

    def _on_tl_seek(self, s: float):
        was_playing = self._playing
        if was_playing:
            self._set_playing(False)

        if self._use_vlc and self.vlc:
            self.vlc.seek(s)
            self.timeline.set_play_pos(s)
        else:
            self._seek_to_cv(s)

        if was_playing:
            self.root.after(200, lambda: self._set_playing(True))

    def _seek_to_cv(self, s: float):
        """OpenCV path: seek + show frame."""
        if self.reader:
            self.reader.seek(s)
        self.timeline.set_play_pos(s)
        self.root.after(80, self._try_show_cv_frame)

    def _try_show_cv_frame(self):
        if self.reader:
            res = self.reader.get_frame()
            if res:
                frame_rgb, pos_s = res
                self._show_cv_frame(frame_rgb)
                self.timeline.set_play_pos(pos_s)
            else:
                self.root.after(60, self._try_show_cv_frame)

    # ─── VLC position update callback ─────────────────────────────────────────

    def _on_vlc_time(self, pos_s: float):
        self.timeline.set_play_pos(pos_s)

    def _on_vlc_end(self):
        self._set_playing(False)

    # ─── Marker set buttons ────────────────────────────────────────────────────

    def _current_time(self) -> float:
        if self._use_vlc and self.vlc:
            return self.vlc.get_time()
        return self.timeline.get_play_s()

    def _set_in_here(self):
        if self.video_info:
            self.timeline.set_in_pos(self._current_time())

    def _set_out_here(self):
        if self.video_info:
            self.timeline.set_out_pos(self._current_time())

    def _set_split_here(self):
        if self.video_info:
            self.timeline.set_split_pos(self._current_time())

    # ─── File loading ──────────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Video files",
                        "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.ts *.mts *.3gp"),
                       ("All files", "*.*")]
        )
        if path:
            self._on_file_loaded(path)

    def _on_file_loaded(self, filepath: str):
        self._set_status("⏳ Đang đọc video...", COLORS["warning"])
        self.root.update_idletasks()

        info = get_video_info(filepath)
        if info is None:
            messagebox.showerror("Lỗi", f"Không đọc được:\n{filepath}")
            self._set_status("❌ Lỗi đọc file", COLORS["danger"])
            return

        # Stop & release old engines
        self._set_playing(False)
        self._cleanup()

        self.video_info = info
        self.video_path = filepath
        self._hide_drop_overlay()

        # ── Start playback engine ──
        if self._use_vlc:
            try:
                self.vlc = VLCPlayer(
                    self.video_frame,
                    on_time_update=self._on_vlc_time,
                    on_end=self._on_vlc_end,
                )
                self.vlc.load(filepath, info["duration_s"])
            except Exception as e:
                self._use_vlc = False
                self.vlc = None
                self._start_cv_reader(filepath, info)
        else:
            self._start_cv_reader(filepath, info)

        # Update timeline
        self.timeline.set_duration(info["duration_s"])

        # Default output dirs
        default_out = os.path.dirname(filepath)
        for mk in ("trim", "split", "compress"):
            e = getattr(self, f"out_entry_{mk}", None)
            if e:
                e.delete(0, "end")
                e.insert(0, default_out)

        # Check compression warning
        if info.get("is_compressed", False):
            self.compress_warning.pack(fill="x", padx=14, pady=(2, 6), before=self.export_row_compress)
        else:
            self.compress_warning.pack_forget()

        # Info bar
        self.info_var.set(
            f"{info['filename']}  •  {info['duration_str']}  •  "
            f"{info['width']}×{info['height']}  •  {info['fps']:.0f}fps  •  "
            f"{info['size_mb']:.1f}MB  •  {info['codec_video'].upper()}"
        )
        self._set_status(f"✅ Đã tải: {info['filename']}", COLORS["success"])
        self._set_progress(0)

    def _start_cv_reader(self, filepath: str, info: dict):
        if not HAS_CV2:
            self._set_status("⚠️ opencv-python chưa được cài đặt", COLORS["warning"])
            return
        cw = max(self.video_canvas.winfo_width(), 640)
        ch = max(self.video_canvas.winfo_height(), 360)
        self.reader = ThreadedReader(filepath, info["fps"], cw, ch)
        self.reader.seek(0)
        self.root.after(120, self._try_show_cv_frame)

    # ─── Cleanup ───────────────────────────────────────────────────────────────

    def _cleanup(self):
        if self.vlc:
            try:
                self.vlc.release()
            except Exception:
                pass
            self.vlc = None
        if self.reader:
            try:
                self.reader.release()
            except Exception:
                pass
            self.reader = None

    # ─── Export ────────────────────────────────────────────────────────────────

    def _browse_output(self, entry: tk.Entry):
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _export(self, mode_key: str):
        if not self.video_info:
            messagebox.showwarning("Chưa có video", "Hãy mở 1 video trước!")
            return
        self._set_playing(False)

        out_dir = getattr(self, f"out_entry_{mode_key}").get().strip()
        if not out_dir:
            out_dir = os.path.dirname(self.video_path)
        os.makedirs(out_dir, exist_ok=True)

        base = os.path.splitext(self.video_info["filename"])[0]
        ext  = os.path.splitext(self.video_info["filename"])[1] or ".mp4"
        ts   = int(time.time())

        if mode_key == "trim":
            in_s, out_s = self.timeline.get_in_s(), self.timeline.get_out_s()
            if out_s <= in_s:
                messagebox.showwarning("Thời gian không hợp lệ",
                                       "Điểm kết thúc phải sau điểm bắt đầu.")
                return
            output = os.path.join(out_dir, f"{base}_trim_{ts}{ext}")
            self._set_status("⏳ Đang cắt...", COLORS["warning"])
            self._set_exporting(mode_key, True)
            self.current_proc = trim_video(
                self.video_path, output, in_s, out_s,
                progress_cb=lambda p: self.root.after(0, self._set_progress, p),
                done_cb=lambda ok, msg: self.root.after(0, self._on_done, ok, msg, output, mode_key),
            )

        elif mode_key == "split":
            split_s = self.timeline.get_split_s()
            out1 = os.path.join(out_dir, f"{base}_part1_{ts}{ext}")
            out2 = os.path.join(out_dir, f"{base}_part2_{ts}{ext}")
            self._set_status("⏳ Đang tách...", COLORS["warning"])
            self._set_exporting(mode_key, True)
            self.current_proc = split_video(
                self.video_path, out1, out2, split_s,
                total_s=self.video_info["duration_s"],
                progress_cb=lambda p: self.root.after(0, self._set_progress, p),
                done_cb=lambda ok, msg: self.root.after(0, self._on_done, ok, msg, [out1, out2], mode_key),
            )

        elif mode_key == "compress":
            codec = {"h264": "libx264", "h265": "libx265"}[self.compress_codec.get()]
            crf   = {"light": 18, "balanced": 23, "strong": 28}[self.compress_quality.get()]
            output = os.path.join(out_dir, f"{base}_compressed_{ts}.mp4")
            self._set_status("⏳ Đang nén...", COLORS["warning"])
            self._set_exporting(mode_key, True)
            self.current_proc = compress_video(
                self.video_path, output, crf=crf, preset="medium", codec=codec,
                total_duration=self.video_info["duration_s"],
                progress_cb=lambda p: self.root.after(0, self._set_progress, p),
                done_cb=lambda ok, msg: self.root.after(0, self._on_done, ok, msg, output, mode_key),
            )

    def _on_done(self, success: bool, msg: str, output, mode_key: str):
        self._set_exporting(mode_key, False)
        self._set_progress(100 if success else 0)
        if success:
            if isinstance(output, list):
                self._set_status(f"✅ Đã tách thành {len(output)} file", COLORS["success"])
                messagebox.showinfo("Hoàn tất", "Video đã tách:\n" + "\n".join(output))
            else:
                sz = os.path.getsize(output) / 1024**2 if os.path.isfile(output) else 0
                self._set_status(f"✅ Xong! {os.path.basename(output)} ({sz:.1f}MB)", COLORS["success"])
                if messagebox.askyesno("Hoàn tất", f"Đã xuất:\n{output}\n\nMở thư mục?"):
                    os.startfile(os.path.dirname(output))
        else:
            self._set_status("❌ Lỗi!", COLORS["danger"])
            messagebox.showerror("Lỗi FFmpeg", msg[:500])

    def _set_exporting(self, mode_key: str, on: bool):
        btn = getattr(self, f"export_btn_{mode_key}", None)
        can = getattr(self, f"cancel_btn_{mode_key}", None)
        if btn:
            btn.configure(
                state="disabled" if on else "normal",
                bg=COLORS["text_muted"] if on else COLORS["accent"],
            )
        if can:
            if on:
                can.pack(side="left", padx=(8, 0))
            else:
                can.pack_forget()

    def _cancel(self):
        if self.current_proc:
            try:
                self.current_proc.kill()
            except Exception:
                pass
        self._set_status("⚠️ Đã hủy", COLORS["warning"])
        self._set_progress(0)
        self._set_exporting(self.mode_var.get(), False)

    # ─── Status ────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color=None):
        self.status_var.set(msg)

    def _set_progress(self, pct: float):
        self.prog_canvas.coords(self._prog_bar, 0, 0, 160 * pct / 100, 6)

    # ─── Auto-Update ───────────────────────────────────────────────────────────

    def _check_update_thread(self):
        from core.updater import check_for_update
        update_info = check_for_update(self.CURRENT_VERSION)
        if update_info:
            self.root.after(1000, self._prompt_update, update_info)

    def _prompt_update(self, update_info: dict):
        ver = update_info["version"]
        url = update_info["download_url"]
        log = update_info.get("changelog", "")
        
        msg = f"Đã tìm thấy phiên bản mới: {ver}\n"
        if log:
            # Clean up long changelogs
            log_lines = log.split("\n")
            if len(log_lines) > 8:
                log = "\n".join(log_lines[:8]) + "\n... (và một số cập nhật khác)"
            msg += f"\nNội dung cập nhật:\n{log}\n"
        msg += "\nBạn có muốn tự động tải về và nâng cấp ứng dụng ngay bây giờ không?"
        
        if messagebox.askyesno("Cập nhật phiên bản mới", msg, parent=self.root):
            self._start_update_download(url, ver)

    def _start_update_download(self, download_url: str, version_tag: str):
        # Create a progress window
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Đang tải cập nhật")
        progress_win.resizable(False, False)
        progress_win.configure(bg=COLORS["bg_card"])
        progress_win.grab_set()
        progress_win.parent = self.root
        
        # Center the window
        progress_win.update_idletasks()
        w, h = 420, 160
        rx = self.root.winfo_x() + self.root.winfo_width() // 2 - w // 2
        ry = self.root.winfo_y() + self.root.winfo_height() // 2 - h // 2
        progress_win.geometry(f"{w}x{h}+{rx}+{ry}")
        
        # UI components
        tk.Label(progress_win, text=f"Đang tải bản cập nhật mới ({version_tag})...", 
                 font=FONTS["subhead"], bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(pady=(20, 10))
                 
        prog_bar = ttk.Progressbar(progress_win, orient="horizontal", length=340, mode="determinate")
        prog_bar.pack(pady=10)
        
        pct_lbl = tk.Label(progress_win, text="0%", font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        pct_lbl.pack(pady=2)
        
        # Progress callback (run in main GUI thread)
        def update_progress(pct: float):
            prog_bar["value"] = pct
            pct_lbl.configure(text=f"{pct:.0f}%")
            
        def on_download_success(new_exe: str):
            from core.updater import apply_update
            try:
                progress_win.destroy()
            except Exception:
                pass
            messagebox.showinfo(
                "Tải hoàn tất!", 
                "Ứng dụng sẽ tự động đóng lại để cài đặt bản cập nhật mới và khởi động lại ngay lập tức.",
                parent=self.root
            )
            apply_update(new_exe)
            self._on_close()
            
        def on_download_fail():
            try:
                progress_win.destroy()
            except Exception:
                pass
            messagebox.showerror(
                "Lỗi cập nhật", 
                "Tải bản cập nhật thất bại. Vui lòng thử lại sau!", 
                parent=self.root
            )
            
        def run_download():
            from core.updater import download_update
            
            def safe_progress(pct):
                self.root.after(0, lambda: update_progress(pct))
                
            new_exe = download_update(download_url, progress_cb=safe_progress)
            
            if new_exe and os.path.isfile(new_exe):
                self.root.after(0, lambda: on_download_success(new_exe))
            else:
                self.root.after(0, on_download_fail)
                
        # Start download in another thread
        import threading
        threading.Thread(target=run_download, daemon=True).start()
