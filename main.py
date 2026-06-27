# main.py — KathTrimmer entry point

import sys
import os
import tkinter as tk

# ── Add project root to path ─────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def check_ffmpeg() -> bool:
    """Return True if ffmpeg/ffprobe are available (bundled or on PATH)."""
    import subprocess
    ffmpeg_path = os.path.join(ROOT, "ffmpeg_bin", "ffmpeg.exe")
    ffprobe_path = os.path.join(ROOT, "ffmpeg_bin", "ffprobe.exe")
    if os.path.isfile(ffmpeg_path) and os.path.isfile(ffprobe_path):
        return True
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, timeout=5,
            creationflags=0x08000000 if sys.platform == "win32" else 0
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            # Set AppUserModelID so Windows taskbar groups windows properly and shows the correct icon
            myappid = 'KathTrimmer.KathTrimmerApp.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    # Use tkinterdnd2 if available (drag & drop)
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except ImportError:
        root = tk.Tk()

    # Make ffmpeg_bin dir if not exists
    os.makedirs(os.path.join(ROOT, "ffmpeg_bin"), exist_ok=True)

    # Build main app immediately (runs the mainloop)
    from ui.app import KathTrimmerApp
    app = KathTrimmerApp(root)

    # After app is built, check FFmpeg and show dialog if needed
    if not check_ffmpeg():
        root.after(300, lambda: _show_ffmpeg_dialog(root))

    root.mainloop()


def _show_ffmpeg_dialog(root: tk.Tk):
    """Non-blocking FFmpeg missing dialog — shown after main window opens."""
    from ui.theme import COLORS, FONTS

    dlg = tk.Toplevel(root)
    dlg.title("Thiếu FFmpeg")
    dlg.resizable(False, False)
    dlg.configure(bg=COLORS["bg_card"])
    dlg.grab_set()
    dlg.lift()
    dlg.focus_force()

    # Center over main window
    dlg.update_idletasks()
    w, h = 480, 280
    rx = root.winfo_x() + root.winfo_width() // 2 - w // 2
    ry = root.winfo_y() + root.winfo_height() // 2 - h // 2
    dlg.geometry(f"{w}x{h}+{rx}+{ry}")

    # ── Header ──
    hdr = tk.Frame(dlg, bg=COLORS["accent"], height=48)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="⚙️  Thiếu FFmpeg",
             font=FONTS["subhead"], fg="white", bg=COLORS["accent"]).pack(side="left", padx=16)

    # ── Body ──
    body = tk.Frame(dlg, bg=COLORS["bg_card"])
    body.pack(fill="both", expand=True, padx=20, pady=14)

    tk.Label(body,
             text="KathTrimmer cần FFmpeg để xử lý video.\nFFmpeg chưa được tìm thấy trên máy của bạn.",
             font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_primary"],
             justify="left", anchor="w").pack(fill="x")

    info = tk.Frame(body, bg=COLORS["accent_bg"])
    info.pack(fill="x", pady=(10, 4))
    tk.Label(info,
             text="📥  Tự động tải (~90MB) và cài vào ứng dụng. Cần kết nối internet (~1–3 phút).",
             font=FONTS["small"], bg=COLORS["accent_bg"], fg=COLORS["accent_dark"],
             justify="left", anchor="w").pack(fill="x", padx=12, pady=8)

    # ── Buttons ──
    btn_row = tk.Frame(body, bg=COLORS["bg_card"])
    btn_row.pack(fill="x", pady=(12, 0))

    def _auto_download():
        dlg.destroy()
        from core.ffmpeg_downloader import FFmpegDownloadDialog
        FFmpegDownloadDialog(root, on_done=lambda ok: None)

    def _skip():
        dlg.destroy()

    tk.Button(btn_row, text="📥  Tự động tải FFmpeg",
              font=FONTS["btn"], bg=COLORS["accent"], fg="white",
              relief="flat", bd=0, padx=20, pady=10, cursor="hand2",
              activebackground=COLORS["accent_dark"],
              command=_auto_download).pack(side="left")

    tk.Button(btn_row, text="Bỏ qua",
              font=FONTS["label"], bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
              relief="flat", bd=0, padx=12, pady=10, cursor="hand2",
              activebackground=COLORS["bg_hover"],
              command=_skip).pack(side="left", padx=(10, 0))

    dlg.protocol("WM_DELETE_WINDOW", _skip)


if __name__ == "__main__":
    main()
