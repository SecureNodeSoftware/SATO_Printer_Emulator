# SATO Printer Emulator

A Windows desktop application that emulates SATO label printers by receiving and rendering SBPL (SATO Barcode Programming Language) formatted print data.

## Features

- **TCP Network Listener** - Listens on a configurable IP/port (default 9100) for incoming SBPL print data
- **SBPL Command Interpreter** - Parses and interprets the SBPL command set including:
  - Text rendering with 12 bitmap fonts (XU, XS, XM, XB, XL, U, S, M, WB, WL, OA, OB)
  - Outline fonts and CG fonts
  - Barcode generation (CODE39, CODE128, EAN-13, EAN-8, UPC-A, CODE93, Interleaved 2of5, and more)
  - Graphics rendering (frames, rulers, raw bitmap data, black/white inversion)
  - Text rotation (0, 90, 180, 270 degrees)
  - Character enlargement (1x-12x)
  - Form overlay registration and recall
- **Visual Label Preview** - Real-time rendering of labels with zoom controls
- **Printer Settings** - Configurable printer model, DPI (203/305), label size, print density
- **Network Configuration** - Configurable listen IP, port, buffer size
- **PNG Export** - Save rendered labels as PNG images at print resolution
- **Job History** - Browse and re-render previously received print jobs
- **Raw Data Viewer** - Hex dump and parsed command view of received SBPL data
- **Test Input** - Built-in sample SBPL data for testing without a network connection

## Supported Printer Models

| Model | DPI | Max Print Width |
|-------|-----|-----------------|
| CL408e | 203 | 832 dots |
| CL412e | 305 | 1248 dots |
| CL608e | 203 | 1216 dots |
| CL612e | 305 | 1984 dots |
| M-8400RVe | 203 | 832 dots |
| CT400DT | 203 | 832 dots |
| CT410DT | 305 | 1248 dots |

## Installation

### From Source

```bash
pip install -r requirements.txt
python run.py
```

### Build Windows Executable

```bash
pip install -r requirements.txt
python build.py
```

The executable will be created at `dist/SATOPrinterEmulator.exe`.

## Usage

1. **Start the application** - Run `python run.py` or the built executable
2. **Configure settings** - Go to Settings > Printer Settings to set:
   - Printer model and DPI
   - Label dimensions (width x height in mm)
   - Network listen address and port
3. **Start the listener** - Click "Start Listener" in the toolbar
4. **Send SBPL data** - Point your application to the emulator's IP:port
5. **View labels** - The rendered label appears in the preview panel
6. **Export** - Use File > Save Label as PNG to export

### Testing Without Network

Use **File > Test Input** or the **Test Input** toolbar button to enter SBPL data manually. Several sample labels are provided including shipping labels, barcode samplers, and text demos.

## Project Structure

```
src/
  main.py              - Application entry point
  config/settings.py   - Configuration management
  parser/
    tokenizer.py       - SBPL byte stream tokenizer
    interpreter.py     - Command interpreter / state machine
  renderer/
    label_renderer.py  - Pillow-based label rendering engine
  fonts/
    bitmap_fonts.py    - SBPL font metrics definitions
  network/
    tcp_server.py      - TCP socket server
  gui/
    main_window.py     - Main application window
    settings_dialog.py - Printer/network settings dialog
    test_input_dialog.py - Manual SBPL input dialog
```

## Requirements

- Python 3.11+
- PyQt6
- Pillow
- python-barcode
- PyInstaller (for building executable)
