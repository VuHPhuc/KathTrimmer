# launcher.py — KathTrimmer Dynamic Launcher
import sys
import os
import ctypes

# Set AppUserModelID so Windows taskbar groups windows properly and shows the correct icon
if sys.platform == "win32":
    try:
        myappid = 'KathTrimmer.KathTrimmerApp.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

# Force PyInstaller to statically package the third-party dependencies of KathTrimmer
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter
import tkinterdnd2
import PIL
import PIL.Image
import PIL.ImageTk
import cv2
import ffmpeg
import vlc
import subprocess
import traceback
import time

# Get the directory of the executable
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    exe_dir = os.path.dirname(os.path.abspath(__file__))

# Add the directory to the beginning of sys.path to prioritize local files
sys.path.insert(0, exe_dir)

if __name__ == "__main__":
    try:
        # Dynamically import and run the local main.py file
        import importlib
        main_module = importlib.import_module("main")
        main_module.main()
    except Exception as e:
        # Show a dialog in case of failure to load local files
        root = tk.Tk()
        root.withdraw()
        error_msg = traceback.format_exc()
        messagebox.showerror(
            "Lỗi Khởi Chạy KathTrimmer",
            f"Không thể khởi chạy ứng dụng từ file code main.py trong thư mục:\n{exe_dir}\n\nChi tiết lỗi:\n{error_msg}"
        )
