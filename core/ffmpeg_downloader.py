# core/ffmpeg_downloader.py — Auto-download FFmpeg binaries

import os
import sys
import zipfile
import threading
import urllib.request
import tkinter as tk
from tkinter import ttk


FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def get_ffmpeg_bin_dir() -> str:
    """Returns the path to the ffmpeg_bin directory."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ffmpeg_bin")


def download_ffmpeg(progress_cb=None, done_cb=None):
    """
    Download ffmpeg-release-essentials.zip, extract ffmpeg.exe + ffprobe.exe
    into the ffmpeg_bin folder.
    progress_cb(percent: float, label: str)
    done_cb(success: bool, message: str)
    """
    ffmpeg_dir = get_ffmpeg_bin_dir()
    os.makedirs(ffmpeg_dir, exist_ok=True)

    tmp_zip = os.path.join(ffmpeg_dir, "_ffmpeg_tmp.zip")

    def _run():
        try:
            # --- Download ---
            def _reporthook(block_num, block_size, total_size):
                if total_size > 0 and progress_cb:
                    pct = min(90.0, block_num * block_size / total_size * 90)
                    progress_cb(pct, f"Đang tải FFmpeg... {pct:.0f}%")

            if progress_cb:
                progress_cb(0, "Đang kết nối tới server...")

            urllib.request.urlretrieve(FFMPEG_DOWNLOAD_URL, tmp_zip, _reporthook)

            # --- Extract ---
            if progress_cb:
                progress_cb(91, "Đang giải nén...")

            with zipfile.ZipFile(tmp_zip, "r") as zf:
                names = zf.namelist()
                for name in names:
                    basename = os.path.basename(name)
                    if basename in ("ffmpeg.exe", "ffprobe.exe"):
                        target = os.path.join(ffmpeg_dir, basename)
                        with zf.open(name) as src, open(target, "wb") as dst:
                            dst.write(src.read())

            if progress_cb:
                progress_cb(99, "Dọn dẹp...")

            # Cleanup
            if os.path.isfile(tmp_zip):
                os.remove(tmp_zip)

            # Verify
            ok = (
                os.path.isfile(os.path.join(ffmpeg_dir, "ffmpeg.exe")) and
                os.path.isfile(os.path.join(ffmpeg_dir, "ffprobe.exe"))
            )

            if progress_cb:
                progress_cb(100, "Hoàn tất!" if ok else "Lỗi!")

            if done_cb:
                done_cb(ok, "FFmpeg đã được cài đặt thành công!" if ok else "Không tìm thấy ffmpeg.exe trong file tải về.")

        except Exception as e:
            if os.path.isfile(tmp_zip):
                try:
                    os.remove(tmp_zip)
                except Exception:
                    pass
            if done_cb:
                done_cb(False, f"Lỗi tải xuống: {str(e)}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


class FFmpegDownloadDialog(tk.Toplevel):
    """
    A modal dialog that shows FFmpeg download progress.
    Calls on_done(success) when finished.
    """

    def __init__(self, parent, on_done=None):
        super().__init__(parent)
        self.on_done = on_done
        self.title("Tải FFmpeg")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Block close during download

        self._build()
        self._center(parent)
        self._start_download()

    def _build(self):
        from ui.theme import COLORS, FONTS

        self.configure(bg=COLORS["bg_card"])

        # Icon + title
        header = tk.Frame(self, bg=COLORS["accent"], height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📥  Tải FFmpeg tự động",
                 font=FONTS["subhead"], fg="white", bg=COLORS["accent"]).pack(side="left", padx=16)

        tk.Label(self, text="Đang tải FFmpeg — thành phần xử lý video...",
                 font=FONTS["body"], bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"]).pack(anchor="w", padx=24, pady=(16, 4))

        # Progress label
        self.lbl_var = tk.StringVar(value="Đang chuẩn bị...")
        self.progress_lbl = tk.Label(self, textvariable=self.lbl_var,
                                      font=FONTS["small"], bg=COLORS["bg_card"],
                                      fg=COLORS["text_secondary"])
        self.progress_lbl.pack(anchor="w", padx=24)

        # Progress bar (canvas)
        bar_frame = tk.Frame(self, bg=COLORS["bg_card"])
        bar_frame.pack(fill="x", padx=24, pady=(8, 16))

        self.bar_canvas = tk.Canvas(bar_frame, height=16, bg=COLORS["slider_track"],
                                     highlightthickness=1,
                                     highlightbackground=COLORS["border"])
        self.bar_canvas.pack(fill="x")
        self.bar_fill = self.bar_canvas.create_rectangle(0, 0, 0, 16,
                                                          fill=COLORS["accent"], outline="")
        self.bar_canvas.bind("<Configure>", self._on_bar_resize)
        self._bar_pct = 0

        # Note
        tk.Label(self, text="⚠️  File tải về ~90MB. Vui lòng đợi...",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["warning"]).pack(padx=24, pady=(0, 16))

        # Cancel button
        self.cancel_btn = tk.Button(
            self, text="Hủy", font=("Segoe UI", 10),
            bg=COLORS["bg_sidebar"], fg=COLORS["danger"],
            relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
            command=self._cancel,
        )
        self.cancel_btn.pack(pady=(0, 16))

        self._cancelled = False

    def _on_bar_resize(self, event):
        w = event.width
        fill_w = w * self._bar_pct / 100
        self.bar_canvas.coords(self.bar_fill, 0, 0, fill_w, 16)

    def _set_progress(self, pct: float, label: str):
        self._bar_pct = pct
        w = self.bar_canvas.winfo_width()
        fill_w = w * pct / 100
        self.bar_canvas.coords(self.bar_fill, 0, 0, fill_w, 16)
        self.lbl_var.set(label)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width() // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        w, h = 440, 230
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def _start_download(self):
        def _progress(pct, label):
            if not self._cancelled:
                self.after(0, self._set_progress, pct, label)

        def _done(success, message):
            if self._cancelled:
                return
            self.after(0, self._on_download_done, success, message)

        download_ffmpeg(progress_cb=_progress, done_cb=_done)

    def _on_download_done(self, success: bool, message: str):
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.cancel_btn.pack_forget()

        from ui.theme import COLORS, FONTS
        if success:
            self.lbl_var.set("✅ " + message)
            self.progress_lbl.configure(fg=COLORS["success"])
            ok_btn = tk.Button(self, text="Tiếp tục →", font=FONTS["btn"],
                               bg=COLORS["accent"], fg="white", relief="flat", bd=0,
                               padx=20, pady=8, cursor="hand2",
                               command=lambda: [self.destroy(), self.on_done(True) if self.on_done else None])
            ok_btn.pack(pady=(0, 16))
        else:
            self.lbl_var.set("❌ " + message)
            self.progress_lbl.configure(fg=COLORS["danger"])
            retry_btn = tk.Button(self, text="Thử lại", font=FONTS["btn"],
                                  bg=COLORS["warning"], fg="white", relief="flat", bd=0,
                                  padx=20, pady=8, cursor="hand2",
                                  command=lambda: [self.destroy(),
                                                   FFmpegDownloadDialog(self.master, self.on_done)])
            retry_btn.pack(side="left", padx=(24, 8), pady=(0, 16))
            skip_btn = tk.Button(self, text="Bỏ qua", font=FONTS["label"],
                                 bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                                 relief="flat", bd=0, padx=12, pady=8, cursor="hand2",
                                 command=lambda: [self.destroy(), self.on_done(False) if self.on_done else None])
            skip_btn.pack(side="left", pady=(0, 16))

    def _cancel(self):
        self._cancelled = True
        self.destroy()
        if self.on_done:
            self.on_done(False)
