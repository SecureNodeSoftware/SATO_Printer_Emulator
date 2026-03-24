"""Build script to package SATO Printer Emulator as a Windows executable."""

import subprocess
import sys
import os


def build():
    """Build the application using PyInstaller."""
    print("Building SATO Printer Emulator...")

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "SATOPrinterEmulator",
        "--onefile",
        "--windowed",
        "--hidden-import", "src.gui",
        "--hidden-import", "src.parser",
        "--hidden-import", "src.renderer",
        "--hidden-import", "src.network",
        "--hidden-import", "src.config",
        "--hidden-import", "src.fonts",
        "--hidden-import", "barcode",
        "--hidden-import", "PIL",
        "--collect-all", "PyQt6",
        "run.py",
    ]

    # Add icon if it exists
    icon_path = os.path.join("resources", "printer.ico")
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    if result.returncode == 0:
        print("\nBuild successful!")
        print("Executable location: dist/SATOPrinterEmulator.exe")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
