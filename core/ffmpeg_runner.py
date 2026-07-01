# core/ffmpeg_runner.py — FFmpeg subprocess wrapper

import subprocess
import threading
import os
import sys
import re
from typing import Callable, Optional


def get_ffmpeg_path():
    """Return path to ffmpeg binary."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for name in ["ffmpeg.exe", "ffmpeg"]:
        bundled = os.path.join(base, "ffmpeg_bin", name)
        if os.path.isfile(bundled):
            return bundled

    return "ffmpeg"


def _parse_time(time_str: str) -> float:
    """Parse ffmpeg time string like '00:01:23.45' to seconds."""
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception:
        pass
    return 0.0


def run_ffmpeg(
    args: list,
    total_duration: float = 0,
    progress_cb: Optional[Callable[[float], None]] = None,
    done_cb: Optional[Callable[[bool, str], None]] = None,
) -> subprocess.Popen:
    """
    Run ffmpeg with the given argument list.
    progress_cb(percent: float 0..100) is called on the main thread.
    done_cb(success: bool, message: str) is called when finished.
    Returns the Popen object so the caller can cancel if needed.
    """
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg, "-y"] + args  # -y = overwrite output without asking

    CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        creationflags=CREATE_NO_WINDOW
    )

    def _reader():
        stderr_lines = []
        time_re = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
        for line in proc.stderr:
            stderr_lines.append(line)
            if progress_cb and total_duration > 0:
                m = time_re.search(line)
                if m:
                    current = _parse_time(m.group(1))
                    pct = min(100.0, current / total_duration * 100)
                    try:
                        progress_cb(pct)
                    except Exception:
                        pass
        proc.wait()
        success = proc.returncode == 0
        msg = "".join(stderr_lines[-20:]) if not success else ""
        if done_cb:
            try:
                done_cb(success, msg)
            except Exception:
                pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return proc


def trim_video(
    input_path: str,
    output_path: str,
    start_s: float,
    end_s: float,
    progress_cb=None,
    done_cb=None,
) -> subprocess.Popen:
    """Lossless trim: extract [start_s, end_s] from input video."""
    duration = end_s - start_s
    args = [
        "-ss", str(start_s),
        "-i", input_path,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path
    ]
    return run_ffmpeg(args, total_duration=duration, progress_cb=progress_cb, done_cb=done_cb)


def split_video(
    input_path: str,
    output_path1: str,
    output_path2: str,
    split_s: float,
    total_s: float,
    progress_cb=None,
    done_cb=None,
) -> list:
    """
    Lossless split at split_s.
    Part 1: [0, split_s], Part 2: [split_s, end].
    Runs two ffmpeg processes sequentially in a thread.
    """
    procs = []

    def _run_both():
        # Part 1
        args1 = [
            "-i", input_path,
            "-t", str(split_s),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path1
        ]
        done1 = threading.Event()
        def _done1(ok, msg):
            done1.set()
        p1 = run_ffmpeg(args1, total_duration=split_s, progress_cb=lambda p: progress_cb(p * 0.5) if progress_cb else None, done_cb=_done1)
        procs.append(p1)
        done1.wait()

        if p1.returncode != 0:
            if done_cb:
                done_cb(False, "Part 1 failed")
            return

        # Part 2
        args2 = [
            "-ss", str(split_s),
            "-i", input_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path2
        ]
        dur2 = total_s - split_s
        done2 = threading.Event()
        def _done2(ok, msg):
            done2.set()
            if done_cb:
                done_cb(ok, msg)
        p2 = run_ffmpeg(args2, total_duration=dur2, progress_cb=lambda p: progress_cb(50 + p * 0.5) if progress_cb else None, done_cb=_done2)
        procs.append(p2)

    t = threading.Thread(target=_run_both, daemon=True)
    t.start()
    return procs


def compress_video(
    input_path: str,
    output_path: str,
    crf: int = 23,
    preset: str = "medium",
    codec: str = "libx264",
    total_duration: float = 0,
    progress_cb=None,
    done_cb=None,
) -> subprocess.Popen:
    """
    Re-encode video with CRF compression.
    codec: 'libx264' (H.264) or 'libx265' (H.265/HEVC, smaller files)
    crf: 18-28 (lower = better quality, larger file). 23 is default.
    preset: ultrafast, fast, medium, slow, veryslow
    """
    args = [
        "-i", input_path,
        "-c:v", codec,
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "copy",  # keep audio unchanged
        "-metadata", "comment=KathTrimmerCompressed",
        output_path
    ]
    return run_ffmpeg(args, total_duration=total_duration, progress_cb=progress_cb, done_cb=done_cb)
