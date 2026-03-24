"""Settings dialog for printer and network configuration."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QGroupBox, QFormLayout, QDialogButtonBox, QSlider,
)
from PyQt6.QtCore import Qt

from src.config.settings import (
    AppConfig, PrinterConfig, NetworkConfig,
    PRINTER_MODELS, DENSITY_LEVELS, OPERATION_MODES,
)


class SettingsDialog(QDialog):
    """Dialog for configuring printer and network settings."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = AppConfig(
            printer=PrinterConfig(**{
                k: getattr(config.printer, k)
                for k in config.printer.__dataclass_fields__
            }),
            network=NetworkConfig(**{
                k: getattr(config.network, k)
                for k in config.network.__dataclass_fields__
            }),
            window_width=config.window_width,
            window_height=config.window_height,
            last_save_dir=config.last_save_dir,
        )
        self.setWindowTitle("Printer Settings")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Printer tab
        printer_tab = QWidget()
        printer_layout = QVBoxLayout(printer_tab)

        # Model selection
        model_group = QGroupBox("Printer Model")
        model_form = QFormLayout(model_group)
        self.model_combo = QComboBox()
        for model_id, info in PRINTER_MODELS.items():
            self.model_combo.addItem(info["description"], model_id)
        idx = self.model_combo.findData(self.config.printer.model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_form.addRow("Model:", self.model_combo)

        self.dpi_label = QLabel(f"{self.config.printer.dpi} DPI")
        model_form.addRow("Print Head Density:", self.dpi_label)
        printer_layout.addWidget(model_group)

        # Label size
        label_group = QGroupBox("Label Size")
        label_form = QFormLayout(label_group)

        self.label_width = QDoubleSpinBox()
        self.label_width.setRange(10.0, 250.0)
        self.label_width.setDecimals(1)
        self.label_width.setSuffix(" mm")
        self.label_width.setValue(self.config.printer.label_width_mm)
        label_form.addRow("Width:", self.label_width)

        self.label_height = QDoubleSpinBox()
        self.label_height.setRange(10.0, 600.0)
        self.label_height.setDecimals(1)
        self.label_height.setSuffix(" mm")
        self.label_height.setValue(self.config.printer.label_height_mm)
        label_form.addRow("Height:", self.label_height)

        self.dots_label = QLabel()
        self._update_dots_label()
        label_form.addRow("Size in dots:", self.dots_label)
        self.label_width.valueChanged.connect(self._update_dots_label)
        self.label_height.valueChanged.connect(self._update_dots_label)
        printer_layout.addWidget(label_group)

        # Print density
        density_group = QGroupBox("Print Density")
        density_form = QFormLayout(density_group)

        self.density_combo = QComboBox()
        for level, name in DENSITY_LEVELS.items():
            self.density_combo.addItem(f"{level} - {name}", level)
        idx = self.density_combo.findData(self.config.printer.density_level)
        if idx >= 0:
            self.density_combo.setCurrentIndex(idx)
        density_form.addRow("Darkness:", self.density_combo)

        self.density_param_combo = QComboBox()
        for p in "ABCDEF":
            self.density_param_combo.addItem(p, p)
        idx = self.density_param_combo.findData(self.config.printer.density_param)
        if idx >= 0:
            self.density_param_combo.setCurrentIndex(idx)
        density_form.addRow("Density Parameter:", self.density_param_combo)
        printer_layout.addWidget(density_group)

        # Operation mode
        mode_group = QGroupBox("Operation Mode")
        mode_form = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        for mode_id, name in OPERATION_MODES.items():
            self.mode_combo.addItem(name, mode_id)
        idx = self.mode_combo.findData(self.config.printer.operation_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        mode_form.addRow("Mode:", self.mode_combo)
        printer_layout.addWidget(mode_group)

        printer_layout.addStretch()
        tabs.addTab(printer_tab, "Printer")

        # Network tab
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)

        net_group = QGroupBox("TCP Server Settings")
        net_form = QFormLayout(net_group)

        self.ip_edit = QLineEdit(self.config.network.ip)
        self.ip_edit.setPlaceholderText("0.0.0.0")
        net_form.addRow("Listen IP:", self.ip_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.config.network.port)
        net_form.addRow("Port:", self.port_spin)

        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1024, 65536)
        self.buffer_spin.setSingleStep(1024)
        self.buffer_spin.setSuffix(" bytes")
        self.buffer_spin.setValue(self.config.network.buffer_size)
        net_form.addRow("Buffer Size:", self.buffer_spin)

        self.max_conn_spin = QSpinBox()
        self.max_conn_spin.setRange(1, 20)
        self.max_conn_spin.setValue(self.config.network.max_connections)
        net_form.addRow("Max Connections:", self.max_conn_spin)

        network_layout.addWidget(net_group)

        info_label = QLabel(
            "<i>Default port 9100 is standard for network printers (RAW/JetDirect).<br>"
            "Use 0.0.0.0 to listen on all interfaces.</i>"
        )
        info_label.setWordWrap(True)
        network_layout.addWidget(info_label)
        network_layout.addStretch()

        tabs.addTab(network_tab, "Network")

        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_model_changed(self, index):
        model_id = self.model_combo.currentData()
        if model_id in PRINTER_MODELS:
            dpi = PRINTER_MODELS[model_id]["dpi"]
            self.dpi_label.setText(f"{dpi} DPI")
            self._update_dots_label()

    def _update_dots_label(self):
        model_id = self.model_combo.currentData()
        dpi = PRINTER_MODELS.get(model_id, PRINTER_MODELS["CL408e"])["dpi"]
        dots_per_mm = dpi / 25.4
        w_dots = int(self.label_width.value() * dots_per_mm)
        h_dots = int(self.label_height.value() * dots_per_mm)
        self.dots_label.setText(f"{w_dots} x {h_dots} dots")

    def _accept(self):
        self.config.printer.model = self.model_combo.currentData()
        self.config.printer.label_width_mm = self.label_width.value()
        self.config.printer.label_height_mm = self.label_height.value()
        self.config.printer.density_level = self.density_combo.currentData()
        self.config.printer.density_param = self.density_param_combo.currentData()
        self.config.printer.operation_mode = self.mode_combo.currentData()
        self.config.network.ip = self.ip_edit.text().strip() or "0.0.0.0"
        self.config.network.port = self.port_spin.value()
        self.config.network.buffer_size = self.buffer_spin.value()
        self.config.network.max_connections = self.max_conn_spin.value()
        self.accept()

    def get_config(self) -> AppConfig:
        return self.config
