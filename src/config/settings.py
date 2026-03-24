"""Configuration management for SATO Printer Emulator."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


# Printer model definitions with their specs
PRINTER_MODELS = {
    "CL408e": {"dpi": 203, "max_h": 832, "max_v": 1424, "description": "CL408e (203 dpi)"},
    "CL412e": {"dpi": 305, "max_h": 1248, "max_v": 2136, "description": "CL412e (305 dpi)"},
    "CL608e": {"dpi": 203, "max_h": 1216, "max_v": 1424, "description": "CL608e (203 dpi, wide)"},
    "CL612e": {"dpi": 305, "max_h": 1984, "max_v": 2136, "description": "CL612e (305 dpi, wide)"},
    "M-8400RVe": {"dpi": 203, "max_h": 832, "max_v": 1424, "description": "M-8400RVe (203 dpi)"},
    "CT400DT": {"dpi": 203, "max_h": 832, "max_v": 3200, "description": "CT400DT (203 dpi)"},
    "CT410DT": {"dpi": 305, "max_h": 1248, "max_v": 4800, "description": "CT410DT (305 dpi)"},
}

DENSITY_LEVELS = {
    1: "Light",
    2: "Medium Light",
    3: "Normal",
    4: "Medium Dark",
    5: "Dark",
}

OPERATION_MODES = {
    0: "Continuous",
    1: "Tear Off",
    2: "Cutter (Head position)",
    3: "Cutter (Cutter position)",
    4: "Cutter (without back feed)",
    7: "Dispenser (Head position)",
    8: "Dispenser (Dispenser position)",
}


@dataclass
class NetworkConfig:
    ip: str = "0.0.0.0"
    port: int = 9100
    buffer_size: int = 4096
    max_connections: int = 5


@dataclass
class PrinterConfig:
    model: str = "CL408e"
    density_level: int = 3
    density_param: str = "A"
    label_width_mm: float = 104.0
    label_height_mm: float = 178.0
    operation_mode: int = 0
    print_speed: int = 5

    @property
    def dpi(self) -> int:
        return PRINTER_MODELS.get(self.model, PRINTER_MODELS["CL408e"])["dpi"]

    @property
    def max_h(self) -> int:
        return PRINTER_MODELS.get(self.model, PRINTER_MODELS["CL408e"])["max_h"]

    @property
    def max_v(self) -> int:
        return PRINTER_MODELS.get(self.model, PRINTER_MODELS["CL408e"])["max_v"]

    @property
    def label_width_dots(self) -> int:
        dots_per_mm = self.dpi / 25.4
        return min(int(self.label_width_mm * dots_per_mm), self.max_h)

    @property
    def label_height_dots(self) -> int:
        dots_per_mm = self.dpi / 25.4
        return min(int(self.label_height_mm * dots_per_mm), self.max_v)


@dataclass
class AppConfig:
    printer: PrinterConfig = field(default_factory=PrinterConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    window_width: int = 1200
    window_height: int = 800
    last_save_dir: str = ""


CONFIG_DIR = Path.home() / ".sato_emulator"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> AppConfig:
    """Load configuration from disk."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            printer = PrinterConfig(**data.get("printer", {}))
            network = NetworkConfig(**data.get("network", {}))
            return AppConfig(
                printer=printer,
                network=network,
                window_width=data.get("window_width", 1200),
                window_height=data.get("window_height", 800),
                last_save_dir=data.get("last_save_dir", ""),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "printer": asdict(config.printer),
        "network": asdict(config.network),
        "window_width": config.window_width,
        "window_height": config.window_height,
        "last_save_dir": config.last_save_dir,
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
