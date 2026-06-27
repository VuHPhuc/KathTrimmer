@echo off
chcp 65001 >nul
echo ================================================
echo   KathTrimmer - Tu dong tai FFmpeg
echo ================================================
echo.
echo Dang tai FFmpeg... (can ket noi internet)
echo.

set FFMPEG_DIR=%~dp0ffmpeg_bin
if not exist "%FFMPEG_DIR%" mkdir "%FFMPEG_DIR%"

:: Download using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip';" ^
  "$zip = '%TEMP%\ffmpeg_release.zip';" ^
  "$extract = '%TEMP%\ffmpeg_extract';" ^
  "Write-Host 'Dang tai...';" ^
  "Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing;" ^
  "Write-Host 'Dang giai nen...';" ^
  "if (Test-Path $extract) { Remove-Item $extract -Recurse -Force };" ^
  "Expand-Archive -Path $zip -DestinationPath $extract -Force;" ^
  "$binDir = Get-ChildItem $extract -Recurse -Directory | Where-Object { $_.Name -eq 'bin' } | Select-Object -First 1;" ^
  "if ($binDir) {" ^
  "  Copy-Item (Join-Path $binDir.FullName 'ffmpeg.exe') '%FFMPEG_DIR%\ffmpeg.exe' -Force;" ^
  "  Copy-Item (Join-Path $binDir.FullName 'ffprobe.exe') '%FFMPEG_DIR%\ffprobe.exe' -Force;" ^
  "  Write-Host 'Hoan thanh!';" ^
  "} else { Write-Host 'Loi: Khong tim thay thu muc bin'; exit 1 };" ^
  "Remove-Item $zip -Force;" ^
  "Remove-Item $extract -Recurse -Force;"

echo.
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    echo [OK] FFmpeg da duoc cai dat vao: %FFMPEG_DIR%
    echo Bay gio ban co the chay: python main.py
) else (
    echo [!] Tai that bai. Vui long tai thu cong tu:
    echo     https://www.gyan.dev/ffmpeg/builds/
    echo     Va sao chep ffmpeg.exe + ffprobe.exe vao thu muc ffmpeg_bin\
)
echo.
pause
