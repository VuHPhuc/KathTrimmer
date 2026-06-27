# ui/drop_zone.py — Drag & Drop zone widget

import tkinter as tk
from tkinter import filedialog
from ui.theme import COLORS, FONTS


class DropZone(tk.Frame):
    """
    A large drag-and-drop zone. Accepts video files.
    Calls on_file_dropped(filepath) when a file is loaded.
    """

    VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
                  ".webm", ".m4v", ".ts", ".mts", ".3gp", ".mpeg", ".mpg"}

    def __init__(self, parent, on_file_dropped, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_file_dropped = on_file_dropped
        self._hovered = False
        self._configure_style()
        self._build_ui()
        self._setup_dnd()

    def _configure_style(self):
        self.configure(
            bg=COLORS["bg_drop"],
            relief="flat",
            bd=0,
        )

    def _build_ui(self):
        # Outer border frame (simulated dashed border via canvas)
        self.canvas = tk.Canvas(
            self,
            bg=COLORS["bg_drop"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._browse_file)

        # Center content frame
        self.center = tk.Frame(self.canvas, bg=COLORS["bg_drop"])
        self.canvas_window = self.canvas.create_window(0, 0, window=self.center, anchor="center")

        # Icon label
        self.icon_lbl = tk.Label(
            self.center,
            text="🎬",
            font=("Segoe UI Emoji", 42),
            bg=COLORS["bg_drop"],
            fg=COLORS["accent"],
        )
        self.icon_lbl.pack(pady=(0, 8))

        self.title_lbl = tk.Label(
            self.center,
            text="Kéo thả video vào đây",
            font=FONTS["heading"],
            bg=COLORS["bg_drop"],
            fg=COLORS["text_primary"],
        )
        self.title_lbl.pack()

        self.sub_lbl = tk.Label(
            self.center,
            text="hoặc click để chọn file  •  MP4, MKV, AVI, MOV...",
            font=FONTS["small"],
            bg=COLORS["bg_drop"],
            fg=COLORS["text_secondary"],
        )
        self.sub_lbl.pack(pady=(4, 0))

    def _on_resize(self, event):
        # Center the window
        self.canvas.coords(self.canvas_window, event.width // 2, event.height // 2)
        self._draw_border(event.width, event.height)

    def _draw_border(self, w, h):
        self.canvas.delete("border")
        r = 14
        dash = (8, 6)
        color = COLORS["accent"] if self._hovered else COLORS["accent_light"]
        # Rounded rectangle approximation
        self.canvas.create_rounded_rectangle = self._rounded_rect
        self._rounded_rect(6, 6, w - 6, h - 6, r, outline=color, dash=dash, width=2, tag="border")

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        tag = kwargs.pop("tag", "")
        color = kwargs.get("outline", COLORS["accent_light"])
        dash = kwargs.get("dash", ())
        width = kwargs.get("width", 1)
        # Arcs for corners
        arc_kw = dict(outline=color, dash=dash, width=width, style="arc", tags=tag)
        self.canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, **arc_kw)
        self.canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, **arc_kw)
        self.canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, **arc_kw)
        self.canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, **arc_kw)
        # Lines for edges (create_line uses 'fill' not 'outline')
        line_kw = dict(fill=color, dash=dash, width=width, tags=tag)
        self.canvas.create_line(x1+r, y1, x2-r, y1, **line_kw)
        self.canvas.create_line(x1+r, y2, x2-r, y2, **line_kw)
        self.canvas.create_line(x1, y1+r, x1, y2-r, **line_kw)
        self.canvas.create_line(x2, y1+r, x2, y2-r, **line_kw)

    def _setup_dnd(self):
        try:
            self.drop_target_register("DND_Files")
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        except Exception:
            pass  # DnD not available (fallback to button click)

    def _on_drag_enter(self, event):
        self._hovered = True
        self._set_hover(True)
        return event.action

    def _on_drag_leave(self, event):
        self._hovered = False
        self._set_hover(False)

    def _on_drop(self, event):
        self._hovered = False
        self._set_hover(False)
        raw = event.data.strip()
        # Handle multiple files or curly-brace wrapping (Windows tkdnd)
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        filepath = raw.split("} {")[0].strip()
        self._load_file(filepath)
        return event.action

    def _browse_file(self, event=None):
        filetypes = [
            ("Video files", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.ts *.mts *.3gp *.mpeg *.mpg"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(filetypes=filetypes, title="Chọn video")
        if path:
            self._load_file(path)

    def _load_file(self, filepath):
        import os
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in self.VIDEO_EXTS:
            return
        if os.path.isfile(filepath):
            self.on_file_dropped(filepath)

    def _set_hover(self, hovered: bool):
        bg = COLORS["bg_drop_hover"] if hovered else COLORS["bg_drop"]
        self.canvas.configure(bg=bg)
        self.center.configure(bg=bg)
        for w in self.center.winfo_children():
            try:
                w.configure(bg=bg)
            except Exception:
                pass
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w > 1 and h > 1:
            self._draw_border(w, h)
