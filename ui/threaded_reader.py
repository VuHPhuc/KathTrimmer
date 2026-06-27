# ui/threaded_reader.py — Sequential-read video reader (OpenCV fallback)

import threading
import queue
import time
import cv2


class ThreadedReader:
    """
    Reads video frames in a background thread using sequential cap.read().
    Uses cap.grab() for skipped frames (no full H.264 decode = fast).
    Outputs RGB frames (BGR→RGB done off main thread).
    """

    QUEUE_SIZE   = 4
    MAX_DISP_FPS = 25   # comfortable display rate for Python/tkinter

    def __init__(self, filepath: str, fps: float, canvas_w: int = 854, canvas_h: int = 480):
        self._filepath = filepath
        self._fps      = max(fps, 1.0)
        # Cap preview resolution (main thread doesn't need to process huge images)
        self._canvas_w = min(canvas_w, 960)
        self._canvas_h = min(canvas_h, 540)

        self._cap = cv2.VideoCapture(filepath)
        try:
            self._cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
        except Exception:
            pass

        total = max(1, self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._duration = total / self._fps

        self._q    = queue.Queue(maxsize=self.QUEUE_SIZE)
        self._lock = threading.Lock()

        self._alive   = True
        self._playing = False
        self._seek_to = None

        # For 60fps source: display every 2nd frame → 30fps display
        self._skip_n = max(1, round(self._fps / self.MAX_DISP_FPS))

        # Wall-clock timing
        self._play_wall = None
        self._play_vid  = None

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # ─── Public API ────────────────────────────────────────────────────────────

    @property
    def duration(self) -> float:
        return self._duration

    def play(self):
        with self._lock:
            self._play_wall = None
            self._play_vid  = None
            self._playing   = True

    def pause(self):
        with self._lock:
            self._playing   = False
            self._play_wall = None

    def seek(self, s: float):
        with self._lock:
            self._seek_to   = max(0.0, min(s, self._duration))
            self._play_wall = None
            self._play_vid  = None
            self._flush()

    def get_frame(self):
        """Non-blocking. Returns (rgb_ndarray, pos_s) or None."""
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def resize_canvas(self, w: int, h: int):
        with self._lock:
            self._canvas_w = min(max(w, 100), 960)
            self._canvas_h = min(max(h, 60),  540)

    def release(self):
        with self._lock:
            self._alive   = False
            self._playing = False
        self._thread.join(timeout=2.0)
        self._cap.release()

    # ─── Worker ────────────────────────────────────────────────────────────────

    def _flush(self):
        """Clear frame queue. Call with lock held."""
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def _worker(self):
        frame_idx = 0

        while True:
            with self._lock:
                if not self._alive:
                    break
                seek_s        = self._seek_to
                self._seek_to = None
                playing       = self._playing
                cw, ch        = self._canvas_w, self._canvas_h
                p_wall        = self._play_wall
                p_vid         = self._play_vid

            # ── Seek ──────────────────────────────────────────────────────────
            if seek_s is not None:
                self._cap.set(cv2.CAP_PROP_POS_MSEC, seek_s * 1000)
                frame_idx = 0
                ret, frame = self._cap.read()
                if ret:
                    pos_s = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    out = self._process(frame, cw, ch)
                    if out is not None:
                        try:
                            self._q.put((out, pos_s), timeout=0.2)
                        except queue.Full:
                            pass
                continue

            if not playing:
                time.sleep(0.016)
                continue

            # ── Playback ──────────────────────────────────────────────────────
            now = time.time()
            if p_wall is None:
                vid_now = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                with self._lock:
                    self._play_wall = now
                    self._play_vid  = vid_now
                p_wall = now
                p_vid  = vid_now

            frame_idx += 1
            display_this = (frame_idx % self._skip_n == 0)

            if display_this:
                ret, frame = self._cap.read()
                if not ret:
                    with self._lock:
                        self._playing   = False
                        self._play_wall = None
                    frame_idx = 0
                    continue

                vid_pos      = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                elapsed_wall = time.time() - p_wall
                elapsed_vid  = vid_pos - p_vid
                ahead        = elapsed_vid - elapsed_wall

                # Throttle if video is ahead of wall clock
                if ahead > 0.04:
                    time.sleep(ahead - 0.02)

                # Drop frame if we're more than 300ms behind
                lag = (time.time() - p_wall) - elapsed_vid
                if lag < 0.3:
                    out = self._process(frame, cw, ch)
                    if out is not None:
                        try:
                            self._q.put_nowait((out, vid_pos))
                        except queue.Full:
                            pass
            else:
                # Grab without decode (fast for H.264)
                ret = self._cap.grab()
                if not ret:
                    with self._lock:
                        self._playing   = False
                        self._play_wall = None
                    frame_idx = 0

    def _process(self, frame_bgr, cw: int, ch: int):
        """Resize + BGR→RGB — both done off the main thread."""
        try:
            fh, fw = frame_bgr.shape[:2]
            if fw == 0 or fh == 0:
                return None
            scale = min(cw / fw, ch / fh)
            nw = max(1, int(fw * scale))
            nh = max(1, int(fh * scale))
            resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
            # Flip channels: BGR → RGB (cheap view + copy)
            return resized[:, :, ::-1].copy()
        except Exception:
            return None
