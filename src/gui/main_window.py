"""Main application window for SATO Printer Emulator."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QToolBar, QPushButton, QStatusBar, QListWidget,
    QListWidgetItem, QTextEdit, QMenuBar, QMenu, QFileDialog,
    QMessageBox, QGroupBox, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QFont
from PIL import Image

from src.config.settings import AppConfig, save_config, load_config
from src.parser.tokenizer import extract_jobs, tokenize_sbpl
from src.parser.interpreter import SBPLInterpreter
from src.renderer.label_renderer import LabelRenderer
from src.network.tcp_server import PrinterTCPServer
from src.gui.settings_dialog import SettingsDialog
from src.gui.test_input_dialog import TestInputDialog

logger = logging.getLogger(__name__)


class LabelPreviewWidget(QWidget):
    """Widget that displays the rendered label image with zoom."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setStyleSheet("background-color: #e0e0e0; border: 1px solid #999;")

        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)

        self._zoom_level = 1.0
        self._current_image: Optional[Image.Image] = None

    def set_image(self, pil_image: Image.Image):
        """Set the displayed label image from a PIL Image."""
        self._current_image = pil_image
        self._update_display()

    def _update_display(self):
        """Update the display with current zoom level."""
        if self._current_image is None:
            self.image_label.setText("No label data received.\n\nStart the listener and send SBPL data,\nor use Test Input to preview a label.")
            return

        img = self._current_image.convert("RGB")
        w = int(img.width * self._zoom_level)
        h = int(img.height * self._zoom_level)
        img = img.resize((w, h), Image.Resampling.NEAREST)

        # Convert to QPixmap
        data = img.tobytes()
        qimage = QImage(data, img.width, img.height, img.width * 3,
                        QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        self.image_label.setPixmap(pixmap)

    def zoom_in(self):
        self._zoom_level = min(8.0, self._zoom_level * 1.5)
        self._update_display()

    def zoom_out(self):
        self._zoom_level = max(0.1, self._zoom_level / 1.5)
        self._update_display()

    def zoom_fit(self):
        if self._current_image is None:
            return
        # Calculate zoom to fit in viewport
        vw = self.scroll_area.viewport().width() - 20
        vh = self.scroll_area.viewport().height() - 20
        iw = self._current_image.width
        ih = self._current_image.height
        if iw > 0 and ih > 0:
            self._zoom_level = min(vw / iw, vh / ih)
            self._update_display()

    def zoom_actual(self):
        self._zoom_level = 1.0
        self._update_display()

    def get_pil_image(self) -> Optional[Image.Image]:
        return self._current_image


class MainWindow(QMainWindow):
    """Main application window."""

    data_received_signal = pyqtSignal(bytes, str)
    client_connected_signal = pyqtSignal(str)
    client_disconnected_signal = pyqtSignal(str)
    server_error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.interpreter = SBPLInterpreter()
        self.renderer = LabelRenderer(self.config.printer)
        self.server: Optional[PrinterTCPServer] = None
        self.job_history: list = []  # list of (timestamp, raw_data, image)

        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._connect_signals()

        self.setWindowTitle("SATO Printer Emulator - SBPL")
        self.resize(self.config.window_width, self.config.window_height)

    def _setup_ui(self):
        """Set up the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Job History
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)

        history_group = QGroupBox("Print Jobs")
        history_layout = QVBoxLayout(history_group)
        self.job_list = QListWidget()
        self.job_list.currentRowChanged.connect(self._on_job_selected)
        history_layout.addWidget(self.job_list)

        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_btn)
        left_layout.addWidget(history_group)

        # Center panel - Label Preview
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(4, 4, 4, 4)

        # Zoom controls
        zoom_bar = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom +")
        zoom_out_btn = QPushButton("Zoom -")
        zoom_fit_btn = QPushButton("Fit")
        zoom_actual_btn = QPushButton("1:1")
        zoom_bar.addWidget(zoom_in_btn)
        zoom_bar.addWidget(zoom_out_btn)
        zoom_bar.addWidget(zoom_fit_btn)
        zoom_bar.addWidget(zoom_actual_btn)
        zoom_bar.addStretch()
        center_layout.addLayout(zoom_bar)

        self.preview = LabelPreviewWidget()
        center_layout.addWidget(self.preview)

        zoom_in_btn.clicked.connect(self.preview.zoom_in)
        zoom_out_btn.clicked.connect(self.preview.zoom_out)
        zoom_fit_btn.clicked.connect(self.preview.zoom_fit)
        zoom_actual_btn.clicked.connect(self.preview.zoom_actual)

        # Right panel - Raw Data Viewer
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)

        raw_group = QGroupBox("Raw SBPL Data")
        raw_layout = QVBoxLayout(raw_group)
        self.raw_data_view = QTextEdit()
        self.raw_data_view.setReadOnly(True)
        self.raw_data_view.setFont(QFont("Courier New", 9))
        raw_layout.addWidget(self.raw_data_view)

        parsed_group = QGroupBox("Parsed Commands")
        parsed_layout = QVBoxLayout(parsed_group)
        self.parsed_view = QTextEdit()
        self.parsed_view.setReadOnly(True)
        self.parsed_view.setFont(QFont("Courier New", 9))
        parsed_layout.addWidget(self.parsed_view)

        right_layout.addWidget(raw_group)
        right_layout.addWidget(parsed_group)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 600, 300])

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.server_status_label = QLabel("Server: Stopped")
        self.status_bar.addPermanentWidget(self.server_status_label)
        self.label_info_label = QLabel("")
        self.status_bar.addWidget(self.label_info_label)

    def _setup_menus(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        save_action = QAction("Save Label as &PNG...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_png)
        file_menu.addAction(save_action)

        save_all_action = QAction("Save &All Labels...", self)
        save_all_action.triggered.connect(self._save_all_png)
        file_menu.addAction(save_all_action)

        file_menu.addSeparator()

        test_action = QAction("&Test Input...", self)
        test_action.setShortcut("Ctrl+T")
        test_action.triggered.connect(self._show_test_input)
        file_menu.addAction(test_action)

        load_file_action = QAction("&Load SBPL File...", self)
        load_file_action.setShortcut("Ctrl+O")
        load_file_action.triggered.connect(self._load_sbpl_file)
        file_menu.addAction(load_file_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")

        prefs_action = QAction("&Printer Settings...", self)
        prefs_action.triggered.connect(self._show_settings)
        settings_menu.addAction(prefs_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Set up the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        self.start_btn = QPushButton("Start Listener")
        self.start_btn.setCheckable(True)
        self.start_btn.clicked.connect(self._toggle_server)
        toolbar.addWidget(self.start_btn)

        toolbar.addSeparator()

        test_btn = QPushButton("Test Input")
        test_btn.clicked.connect(self._show_test_input)
        toolbar.addWidget(test_btn)

        toolbar.addSeparator()

        save_btn = QPushButton("Save PNG")
        save_btn.clicked.connect(self._save_png)
        toolbar.addWidget(save_btn)

    def _connect_signals(self):
        """Connect cross-thread signals."""
        self.data_received_signal.connect(self._handle_data)
        self.client_connected_signal.connect(self._on_client_connected)
        self.client_disconnected_signal.connect(self._on_client_disconnected)
        self.server_error_signal.connect(self._on_server_error)

    # --- Server Control ---

    def _toggle_server(self, checked: bool):
        """Start or stop the TCP server."""
        if checked:
            self._start_server()
        else:
            self._stop_server()

    def _start_server(self):
        """Start the TCP listener."""
        try:
            self.server = PrinterTCPServer(
                config=self.config.network,
                on_data_received=lambda data, addr: self.data_received_signal.emit(data, addr),
                on_client_connected=lambda addr: self.client_connected_signal.emit(addr),
                on_client_disconnected=lambda addr: self.client_disconnected_signal.emit(addr),
                on_error=lambda msg: self.server_error_signal.emit(msg),
            )
            self.server.start()
            self.start_btn.setText("Stop Listener")
            addr = f"{self.config.network.ip}:{self.config.network.port}"
            self.server_status_label.setText(f"Server: Listening on {addr}")
            self.status_bar.showMessage(f"Server started on {addr}", 3000)
        except OSError as e:
            self.start_btn.setChecked(False)
            QMessageBox.critical(self, "Server Error",
                                 f"Failed to start server:\n{e}\n\n"
                                 f"Check that port {self.config.network.port} is available.")

    def _stop_server(self):
        """Stop the TCP listener."""
        if self.server:
            self.server.stop()
            self.server = None
        self.start_btn.setText("Start Listener")
        self.start_btn.setChecked(False)
        self.server_status_label.setText("Server: Stopped")
        self.status_bar.showMessage("Server stopped", 3000)

    # --- Data Handling ---

    def _handle_data(self, data: bytes, client_addr: str):
        """Handle received SBPL data (called on main thread via signal)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._process_sbpl_data(data, f"[{timestamp}] {client_addr}")

    def _process_sbpl_data(self, data: bytes, source: str = ""):
        """Process SBPL data: parse, interpret, render, display."""
        # Parse into jobs
        jobs = extract_jobs(data)
        if not jobs:
            self.status_bar.showMessage("No valid SBPL jobs found in data", 3000)
            return

        # Update raw data view
        self._display_raw_data(data)

        for job in jobs:
            # Interpret
            instructions = self.interpreter.interpret_job(job)

            # Display parsed commands
            self._display_parsed_commands(job)

            # Render
            self.renderer = LabelRenderer(self.config.printer)
            image = self.renderer.render(instructions)

            # Store in history (use job's raw_data, not the full receive buffer)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.job_history.append((timestamp, job.raw_data, image))

            # Add to job list
            item = QListWidgetItem(f"{source or timestamp} - {job.quantity} label(s)")
            self.job_list.addItem(item)
            self.job_list.setCurrentItem(item)

            # Display
            self.preview.set_image(image)

            # Update status
            w = self.config.printer.label_width_dots
            h = self.config.printer.label_height_dots
            self.label_info_label.setText(
                f"Label: {w}x{h} dots | "
                f"{self.config.printer.label_width_mm}x{self.config.printer.label_height_mm}mm | "
                f"{self.config.printer.dpi} DPI | "
                f"{len(instructions)} render instructions"
            )

    def _display_raw_data(self, data: bytes):
        """Display raw SBPL data in hex and ASCII."""
        hex_lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            hex_lines.append(f"{i:04X}  {hex_part:<48}  {ascii_part}")
        self.raw_data_view.setText("\n".join(hex_lines))

    def _display_parsed_commands(self, job):
        """Display parsed SBPL commands."""
        lines = []
        for cmd in job.commands:
            params_display = cmd.params[:50] + "..." if len(cmd.params) > 50 else cmd.params
            lines.append(f"<{cmd.command}> {params_display}")
        self.parsed_view.setText("\n".join(lines))

    # --- Job History ---

    def _on_job_selected(self, row: int):
        """Display a previously received job."""
        if 0 <= row < len(self.job_history):
            _, data, image = self.job_history[row]
            self.preview.set_image(image)
            self._display_raw_data(data)

    def _clear_history(self):
        """Clear job history."""
        self.job_history.clear()
        self.job_list.clear()
        self.raw_data_view.clear()
        self.parsed_view.clear()
        self.preview.set_image(None)
        self.preview._current_image = None
        self.preview._update_display()

    # --- File Operations ---

    def _save_png(self):
        """Save current label as PNG."""
        image = self.preview.get_pil_image()
        if image is None:
            QMessageBox.information(self, "No Label", "No label to save. Receive or input SBPL data first.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Label as PNG",
            self.config.last_save_dir or "",
            "PNG Files (*.png);;All Files (*)"
        )
        if filepath:
            if not filepath.lower().endswith(".png"):
                filepath += ".png"
            # Save without mutating the renderer's current image
            output = image.convert("L")
            dpi = self.config.printer.dpi
            output.save(filepath, "PNG", dpi=(dpi, dpi))
            self.config.last_save_dir = str(Path(filepath).parent)
            save_config(self.config)
            self.status_bar.showMessage(f"Saved: {filepath}", 3000)

    def _save_all_png(self):
        """Save all labels in history as PNG files."""
        if not self.job_history:
            QMessageBox.information(self, "No Labels", "No labels in history to save.")
            return

        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory for Label Export",
            self.config.last_save_dir or ""
        )
        if directory:
            for i, (timestamp, _, image) in enumerate(self.job_history):
                safe_ts = timestamp.replace(":", "-").replace(" ", "_")
                filepath = f"{directory}/label_{i+1:03d}_{safe_ts}.png"
                output = image.convert("L")
                output.save(filepath, "PNG", dpi=(self.config.printer.dpi, self.config.printer.dpi))
            self.config.last_save_dir = directory
            save_config(self.config)
            self.status_bar.showMessage(f"Saved {len(self.job_history)} labels to {directory}", 5000)

    def _load_sbpl_file(self):
        """Load SBPL data from a file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load SBPL File",
            "",
            "SBPL Files (*.sbpl *.prn *.txt *.bin);;All Files (*)"
        )
        if filepath:
            try:
                with open(filepath, "rb") as f:
                    data = f.read()
                self._process_sbpl_data(data, f"File: {Path(filepath).name}")
            except (IOError, OSError) as e:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")

    # --- Dialogs ---

    def _show_test_input(self):
        """Show test input dialog for manual SBPL entry."""
        dialog = TestInputDialog(self)
        if dialog.exec():
            data = dialog.get_sbpl_data()
            if data:
                self._process_sbpl_data(data, "Test Input")

    def _show_settings(self):
        """Show printer settings dialog."""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.config = dialog.get_config()
            save_config(self.config)
            self.renderer = LabelRenderer(self.config.printer)
            self.status_bar.showMessage("Settings updated", 3000)

            # Restart server if running with new network settings
            if self.server and self.server.is_running:
                self._stop_server()
                self.start_btn.setChecked(True)
                self._start_server()

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About SATO Printer Emulator",
            "<h3>SATO Printer Emulator</h3>"
            "<p>A desktop application that emulates SATO label printers by "
            "receiving and rendering SBPL (SATO Barcode Programming Language) "
            "formatted print data.</p>"
            "<p>Listens on a configurable TCP port and visually renders "
            "labels for testing and development.</p>"
            "<p><b>Supported SBPL Commands:</b><br>"
            "Text: XU, XS, XM, XB, XL, U, S, M, WB, WL, OA, OB<br>"
            "Outline Fonts: $, $=, RD<br>"
            "Barcodes: B, D, BD, BG, BC, BI, BP<br>"
            "Graphics: FW, G, (<br>"
            "Control: A, Z, Q, H, V, P, L, E, %, F, &, /</p>"
        )

    # --- Client Events ---

    def _on_client_connected(self, addr: str):
        self.status_bar.showMessage(f"Client connected: {addr}", 3000)

    def _on_client_disconnected(self, addr: str):
        self.status_bar.showMessage(f"Client disconnected: {addr}", 3000)

    def _on_server_error(self, msg: str):
        QMessageBox.warning(self, "Server Error", msg)

    # --- Window Events ---

    def closeEvent(self, event):
        """Handle window close."""
        self._stop_server()
        self.config.window_width = self.width()
        self.config.window_height = self.height()
        save_config(self.config)
        event.accept()
