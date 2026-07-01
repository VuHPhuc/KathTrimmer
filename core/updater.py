# core/updater.py — GitHub Auto-Updater Helper

import os
import sys
import json
import urllib.request
import subprocess

GITHUB_RELEASE_API = "https://api.github.com/repos/VuHPhuc/KathTrimmer/releases/latest"


def parse_version(v_str: str):
    # Strip 'v' or 'V' prefix
    v_str = v_str.lower().lstrip('v').strip()
    try:
        return [int(x) for x in v_str.split('.')]
    except ValueError:
        return [0]


def is_newer(latest_version: str, current_version: str) -> bool:
    return parse_version(latest_version) > parse_version(current_version)


def check_for_update(current_version: str) -> dict | None:
    """
    Check GitHub Releases for a newer version.
    Returns dict if update available, otherwise None.
    """
    try:
        req = urllib.request.Request(
            GITHUB_RELEASE_API,
            headers={"User-Agent": "KathTrimmer-Updater"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        tag_name = data.get("tag_name", "")
        if not tag_name:
            return None
            
        if is_newer(tag_name, current_version):
            # Find the KathTrimmer.exe asset
            assets = data.get("assets", [])
            download_url = None
            for asset in assets:
                if asset.get("name") == "KathTrimmer.exe":
                    download_url = asset.get("browser_download_url")
                    break
            
            if download_url:
                return {
                    "version": tag_name,
                    "download_url": download_url,
                    "changelog": data.get("body", "")
                }
    except Exception as e:
        print(f"Error checking for updates: {e}")
    return None


def download_update(download_url: str, progress_cb=None) -> str | None:
    """
    Download the updated EXE to a temporary file.
    progress_cb(pct: float)
    Returns path to downloaded file, or None on failure.
    """
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        target_path = os.path.join(base_dir, "KathTrimmer_new.exe")
        
        # Download with progress
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "KathTrimmer-Updater"}
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 4096 * 8
            
            with open(target_path, 'wb') as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    f.write(buffer)
                    if total_size > 0 and progress_cb:
                        pct = min(100.0, (downloaded / total_size) * 100)
                        progress_cb(pct)
                        
        return target_path
    except Exception as e:
        print(f"Error downloading update: {e}")
        if os.path.isfile(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        return None


def apply_update(new_exe_path: str):
    """
    Execute the PowerShell script to replace the old EXE with the new one and restart.
    """
    try:
        if getattr(sys, 'frozen', False):
            exe_path = os.path.abspath(sys.executable)
        else:
            exe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "KathTrimmer.exe")
            
        new_exe_path = os.path.abspath(new_exe_path)
        
        # PowerShell command:
        # 1. Wait for 1.5 seconds for this parent process to die
        # 2. Overwrite the old EXE with the new EXE
        # 3. Start the newly overwritten EXE
        cmd = f'Start-Sleep -Milliseconds 1500; Move-Item -Path "{new_exe_path}" -Destination "{exe_path}" -Force; Start-Process "{exe_path}"'
        
        # Run PowerShell in background (no console window)
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            creationflags=0x08000000 if sys.platform == "win32" else 0
        )
    except Exception as e:
        print(f"Error applying update: {e}")
