# core/video_info.py — Read video metadata using ffprobe

import subprocess
import json
import os
import sys


def get_ffprobe_path():
    """Return the path to ffprobe binary."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Check bundled ffprobe first
    for name in ["ffprobe.exe", "ffprobe"]:
        bundled = os.path.join(base, "ffmpeg_bin", name)
        if os.path.isfile(bundled):
            return bundled

    # Fallback: system PATH
    return "ffprobe"


def get_video_info(filepath: str) -> dict:
    """
    Returns a dict with:
        duration_s   - float seconds
        duration_str - "HH:MM:SS.mmm"
        width, height
        codec_video, codec_audio
        fps          - float
        bitrate_kbps - int
        size_mb      - float
        filename     - basename
    Returns None on failure.
    """
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        filepath
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        data = json.loads(result.stdout)
    except Exception as e:
        print(f"ffprobe error: {e}")
        return None

    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

    try:
        duration = float(fmt.get("duration", 0))
    except (ValueError, TypeError):
        duration = 0.0

    try:
        bitrate_kbps = int(fmt.get("bit_rate", 0)) // 1000
    except (ValueError, TypeError):
        bitrate_kbps = 0

    # Parse FPS
    fps = 0.0
    fps_str = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except Exception:
        pass

    size_bytes = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
    size_mb = size_bytes / (1024 * 1024)

    # Check if the video has already been compressed
    tags = fmt.get("tags", {}) or {}
    comment = tags.get("comment", "")
    is_compressed = False
    if "KathTrimmerCompressed" in comment or "compressed" in os.path.basename(filepath).lower():
        is_compressed = True
    else:
        # Calculate BPP (Bits Per Pixel) to detect low-bitrate pre-compressed videos
        try:
            width = int(video_stream.get("width", 0) or 0)
            height = int(video_stream.get("height", 0) or 0)
            if width > 0 and height > 0 and fps > 0 and duration > 0:
                avg_bitrate_bps = (size_bytes * 8) / duration
                bpp = avg_bitrate_bps / (width * height * fps)
                # BPP < 0.1 is standard web compression (low bitrate)
                if bpp < 0.1:
                    is_compressed = True
        except Exception:
            pass

    return {
        "duration_s":   duration,
        "duration_str": seconds_to_str(duration),
        "width":        video_stream.get("width", 0),
        "height":       video_stream.get("height", 0),
        "codec_video":  video_stream.get("codec_name", "N/A"),
        "codec_audio":  audio_stream.get("codec_name", "N/A"),
        "fps":          fps,
        "bitrate_kbps": bitrate_kbps,
        "size_mb":      size_mb,
        "filename":     os.path.basename(filepath),
        "filepath":     filepath,
        "is_compressed": is_compressed,
    }


def seconds_to_str(seconds: float, show_ms: bool = True) -> str:
    """Convert float seconds to HH:MM:SS or HH:MM:SS.mmm"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if show_ms:
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def str_to_seconds(time_str: str) -> float:
    """Convert HH:MM:SS or HH:MM:SS.mmm to float seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            h = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m = float(parts[0])
            s = float(parts[1])
            return m * 60 + s
        else:
            return float(parts[0])
    except Exception:
        return 0.0
