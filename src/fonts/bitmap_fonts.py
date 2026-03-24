"""Bitmap font definitions for SBPL fonts.

Each font is defined by its base character size in dots (width x height).
We use Pillow's built-in bitmap fonts and scale to match SBPL specifications.
For pixel-accurate rendering, we define character metrics for each font type.
"""

from dataclasses import dataclass


@dataclass
class FontMetrics:
    """Metrics for an SBPL bitmap font."""
    name: str
    base_width: int  # dots
    base_height: int  # dots
    has_smoothing: bool = False
    proportional: bool = False


# Font definitions from SBPL spec (8 dots/mm printer - 203 dpi)
FONT_METRICS = {
    "XU": FontMetrics("XU", 5, 9),
    "XS": FontMetrics("XS", 17, 17, proportional=True),
    "XM": FontMetrics("XM", 24, 24, proportional=True),
    "XB": FontMetrics("XB", 48, 48, has_smoothing=True, proportional=True),
    "XL": FontMetrics("XL", 48, 48, has_smoothing=True, proportional=True),
    "U": FontMetrics("U", 5, 9),
    "S": FontMetrics("S", 8, 15),
    "M": FontMetrics("M", 13, 20),
    "WB": FontMetrics("WB", 18, 30, has_smoothing=True),
    "WL": FontMetrics("WL", 28, 52, has_smoothing=True),
    "OA": FontMetrics("OA", 15, 22),  # OCR-A at 203dpi
    "OB": FontMetrics("OB", 20, 24),  # OCR-B at 203dpi
}

# Font definitions for 12 dots/mm printer (305 dpi)
FONT_METRICS_305 = {
    "XU": FontMetrics("XU", 5, 9),
    "XS": FontMetrics("XS", 17, 17, proportional=True),
    "XM": FontMetrics("XM", 24, 24, proportional=True),
    "XB": FontMetrics("XB", 48, 48, has_smoothing=True, proportional=True),
    "XL": FontMetrics("XL", 48, 48, has_smoothing=True, proportional=True),
    "U": FontMetrics("U", 5, 9),
    "S": FontMetrics("S", 8, 15),
    "M": FontMetrics("M", 13, 20),
    "WB": FontMetrics("WB", 18, 30, has_smoothing=True),
    "WL": FontMetrics("WL", 28, 52, has_smoothing=True),
    "OA": FontMetrics("OA", 22, 33),  # OCR-A at 305dpi
    "OB": FontMetrics("OB", 30, 36),  # OCR-B at 305dpi
}


def get_font_metrics(font_name: str, dpi: int = 203) -> FontMetrics:
    """Get font metrics for a given font and DPI."""
    if dpi >= 300:
        return FONT_METRICS_305.get(font_name, FONT_METRICS_305["XM"])
    return FONT_METRICS.get(font_name, FONT_METRICS["XM"])
