# ui/vlc_player.py — Hardware-accelerated video player via embedded VLC

import sys
import tkinter as tk

_VLC_AVAILABLE = False
_vlc = None

def _try_import_vlc():
    global _VLC_AVAILABLE, _vlc
    if _vlc is not None:
        return _VLC_AVAILABLE
    try:
        import vlc as _vlc_mod
        # Quick smoke-test: can we create an Instance?
        test = _vlc_mod.Instance(["--quiet"])
        if test:
            test.release()
            _vlc = _vlc_mod
            _VLC_AVAILABLE = True
    except Exception:
        _VLC_AVAILABLE = False
    return _VLC_AVAILABLE


def vlc_available() -> bool:
    return _try_import_vlc()


class VLCPlayer:
    """
    Embeds VLC directly into a tkinter Frame using the Win32 HWND.
    VLC does all decoding in its own thread with hardware acceleration —
    zero Python frame-copy, zero PIL, zero OpenCV in the playback path.

    Usage:
        player = VLCPlayer(frame_widget)
        player.load(filepath, duration_s)
        player.play()
        player.pause()
        player.seek(30.5)       # seconds
        time_s = player.get_time()
        player.release()
    """

    def __init__(self, frame: tk.Widget,
                 on_time_update=None,   # callback(pos_seconds)
                 on_end=None):          # callback()
        if not _try_import_vlc():
            raise RuntimeError("VLC is not installed on this system.")

        self._frame = frame
        self.on_time_update = on_time_update
        self.on_end = on_end
        self._duration = 0.0
        self._poll_id  = None
        self._hwnd_set = False

        # VLC instance with hardware decoding + quiet mode
        vlc_args = [
            "--quiet",
            "--no-video-title-show",
            "--video-on-top=0",
            "--avcodec-hw=any",      # Enable DXVA2 / D3D11 hardware decoding
            "--input-fast-seek",
            "--network-caching=300",
        ]
        self.instance = _vlc.Instance(vlc_args)
        self.player   = self.instance.media_player_new()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _ensure_hwnd(self):
        """Bind VLC render output to the tkinter frame's Win32 HWND."""
        if self._hwnd_set:
            return
        self._frame.update_idletasks()
        hwnd = self._frame.winfo_id()
        if hwnd and sys.platform == "win32":
            self.player.set_hwnd(hwnd)
            self._hwnd_set = True

    def load(self, filepath: str, duration: float = 0.0):
        """Load a file. Shows the first frame paused."""
        self._ensure_hwnd()
        self._duration = duration

        media = self.instance.media_new(filepath)
        self.player.set_media(media)
        media.release()

        # Play briefly → pause to display the first frame
        self.player.play()
        self._frame.after(250, self._initial_pause)
        self._start_poll()

    def _initial_pause(self):
        self.player.pause()
        # Read actual duration from VLC (more accurate than ffprobe for some formats)
        dur_ms = self.player.get_length()
        if dur_ms > 0:
            self._duration = dur_ms / 1000.0

    # ── Controls ──────────────────────────────────────────────────────────────

    def play(self):
        self._ensure_hwnd()
        self.player.play()

    def pause(self):
        self.player.pause()

    def toggle(self):
        if self.player.is_playing():
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        return bool(self.player.is_playing())

    def get_time(self) -> float:
        """Current playback position in seconds."""
        t = self.player.get_time()
        return max(0.0, t / 1000.0)

    def seek(self, seconds: float):
        """Seek to position in seconds."""
        ms = int(max(0.0, seconds) * 1000)
        self.player.set_time(ms)

    def stop(self):
        self.player.stop()

    def release(self):
        if self._poll_id:
            try:
                self._frame.after_cancel(self._poll_id)
            except Exception:
                pass
        self.player.stop()
        self.player.release()
        self.instance.release()

    # ── Position polling ──────────────────────────────────────────────────────

    def _start_poll(self):
        if self._poll_id:
            try:
                self._frame.after_cancel(self._poll_id)
            except Exception:
                pass
        self._poll()

    def _poll(self):
        if self.player.is_playing():
            pos_s = self.get_time()
            if self.on_time_update:
                try:
                    self.on_time_update(pos_s)
                except Exception:
                    pass
            # Auto-stop at end
            if self._duration > 0 and pos_s >= self._duration - 0.4:
                self.pause()
                if self.on_end:
                    try:
                        self.on_end()
                    except Exception:
                        pass
        self._poll_id = self._frame.after(50, self._poll)
