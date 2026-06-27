@echo off
chcp 65001 >nul
echo ================================================
echo   KathTrimmer - Build Launcher EXE
echo ================================================
echo.

echo [*] Dang build KathTrimmer.exe (Launcher) ...
echo.

python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "KathTrimmer" ^
  --icon "assets\icon.ico" ^
  --hidden-import "tkinterdnd2" ^
  --hidden-import "PIL._tkinter_finder" ^
  --collect-all "customtkinter" ^
  --collect-all "tkinterdnd2" ^
  launcher.py

echo.
if exist "dist\KathTrimmer.exe" (
    echo [*] Dang sao chep KathTrimmer.exe ra thu muc goc ...
    copy /y "dist\KathTrimmer.exe" "KathTrimmer.exe" >nul
    echo [*] Dang tao Shortcut (.lnk) an toan tranh Smart App Control...
    python create_shortcut.py
    echo ================================================
    echo   [OK] Build thanh cong!
    echo   File: KathTrimmer.exe (da dua ra thu muc goc)
    echo   File Shortcut: KathTrimmer.lnk (Khuyên dùng nếu bị Smart App Control chặn)
    echo ================================================
) else (
    echo [!] Build that bai. Kiem tra log phia tren.
)
pause
