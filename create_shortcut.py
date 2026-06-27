# create_shortcut.py
import os
import sys
import pythoncom
from win32com.shell import shell
from win32com.propsys import propsys, pscon

def create_shortcut():
    # Paths
    project_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(project_dir, "main.py")
    icon_path = os.path.join(project_dir, "assets", "icon.ico")
    
    # Get pythonw.exe path
    pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable  # fallback
        
    shortcut_path = os.path.join(project_dir, "KathTrimmer.lnk")
    
    try:
        # 1. CoCreateInstance to create ShellLink COM object
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, 
            None, 
            pythoncom.CLSCTX_INPROC_SERVER, 
            shell.IID_IShellLink
        )
        
        # Set shortcut target, arguments, working dir, and icon
        link.SetPath(pythonw_path)
        link.SetArguments(f'"{main_py}"')
        link.SetWorkingDirectory(project_dir)
        link.SetIconLocation(icon_path, 0)
        link.SetDescription("KathTrimmer - Video Cutter & Compressor")
        
        # 2. Query interface for IPropertyStore to set AppUserModelID
        prop_store = link.QueryInterface(propsys.IID_IPropertyStore)
        appid = 'KathTrimmer.KathTrimmerApp.1.0'
        
        # Write AppUserModelID to the shortcut metadata
        prop_store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(appid))
        prop_store.Commit()
        
        # 3. Save the shortcut link to disk using IPersistFile interface
        persist_file = link.QueryInterface(pythoncom.IID_IPersistFile)
        persist_file.Save(shortcut_path, True)
        
        print(f"[OK] Da tao shortcut an toan voi AppUserModelID tai: {shortcut_path}")
    except Exception as e:
        print(f"[!] Loi khi tao shortcut: {e}")

if __name__ == "__main__":
    create_shortcut()
