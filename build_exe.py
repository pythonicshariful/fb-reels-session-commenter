import os
import shutil
import subprocess
import sys
from pathlib import Path

def build():
    # 1. Install PyInstaller if not present
    print("Ensuring PyInstaller is installed...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 2. Get customtkinter path
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    print(f"Found customtkinter at: {ctk_path}")

    # 3. Define the command
    # --noconfirm: Overwrite existing build
    # --onedir: Easier for debugging/assets (or --onefile for a single exe)
    # --windowed: No console window
    # --add-data: Include customtkinter assets (syntax varies by OS, this is for Windows)
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile", # Single executable
        "--windowed", # Hide console
        "--name", "FB_Reels_AutoCommenter",
        f"--add-data={ctk_path};customtkinter/",
        "gui_app.py"
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "="*50)
        print("SUCCESS! Your EXE is in the 'dist' folder.")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("BUILD FAILED. Check errors above.")
        print("="*50)

if __name__ == "__main__":
    # Clean old builds if they exist
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    if os.path.exists("FB_Reels_AutoCommenter.spec"):
        os.remove("FB_Reels_AutoCommenter.spec")

    build()
