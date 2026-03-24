"""Test input dialog for manually entering SBPL data."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QDialogButtonBox, QComboBox, QGroupBox,
)
from PyQt6.QtGui import QFont

# Sample SBPL commands for testing
SAMPLES = {
    "Simple Text Label": (
        "\x1bA"
        "\x1bV100\x1bH50\x1bL0404\x1bXB1SATO"
        "\x1bV350\x1bH100\x1bB104250*12345*"
        "\x1bV600\x1bH150\x1bL0101\x1bXB 1*12345*"
        "\x1bQ1"
        "\x1bZ"
    ),
    "Rotated Text": (
        "\x1bA"
        "\x1b%0"
        "\x1bV700\x1bH400\x1bL0101\x1bXB0LAB0"
        "\x1b%1"
        "\x1bV700\x1bH400\x1bL0101\x1bXB0LAB1"
        "\x1b%2"
        "\x1bV700\x1bH400\x1bL0101\x1bXB0LAB2"
        "\x1b%3"
        "\x1bV700\x1bH400\x1bL0101\x1bXB0LAB3"
        "\x1bQ1"
        "\x1bZ"
    ),
    "Frame with Text": (
        "\x1bA"
        "\x1bV100\x1bH50\x1bFW1010V800H750"
        "\x1bV100\x1bH50\x1bFW0505V760H710"
        "\x1bV150\x1bH100\x1bL0202\x1bXB0MODEL"
        "\x1bV400\x1bH100\x1bL0101\x1b$B, 100, 100, 0\x1b$=SATO PRINTER"
        "\x1bQ1"
        "\x1bZ"
    ),
    "Multiple Fonts": (
        "\x1bA"
        "\x1bV50\x1bH50\x1bL0101\x1bXUTiny XU Font"
        "\x1bV80\x1bH50\x1bL0101\x1bXSSmall XS Font"
        "\x1bV120\x1bH50\x1bL0101\x1bXMMedium XM Font"
        "\x1bV180\x1bH50\x1bL0101\x1bXB0Large XB Font"
        "\x1bV260\x1bH50\x1bL0101\x1bWB0Wide WB Font"
        "\x1bV320\x1bH50\x1bL0101\x1bUU Font"
        "\x1bV350\x1bH50\x1bL0101\x1bSS Font"
        "\x1bV380\x1bH50\x1bL0101\x1bMM Font"
        "\x1bQ1"
        "\x1bZ"
    ),
    "Barcode Sampler": (
        "\x1bA"
        "\x1bV50\x1bH50\x1bL0101\x1bXMCODE39:"
        "\x1bV80\x1bH50\x1bB103120*HELLO*"
        "\x1bV250\x1bH50\x1bL0101\x1bXMCODE128:"
        "\x1bV280\x1bH50\x1bBG03120SATO12345"
        "\x1bV450\x1bH50\x1bL0101\x1bXMEAN-13:"
        "\x1bV480\x1bH50\x1bB303120012345678901"
        "\x1bQ1"
        "\x1bZ"
    ),
    "Shipping Label": (
        "\x1bA"
        "\x1bV20\x1bH20\x1bFW0404V1380H800"
        "\x1bV40\x1bH40\x1bL0303\x1bXB1SATO Corp"
        "\x1bV150\x1bH40\x1bL0101\x1bXM123 Industrial Way"
        "\x1bV190\x1bH40\x1bL0101\x1bXMTokyo, Japan 100-0001"
        "\x1bV250\x1bH20\x1bFW0202H760"
        "\x1bV280\x1bH40\x1bL0101\x1bXMSHIP TO:"
        "\x1bV320\x1bH40\x1bL0202\x1bXB1John Smith"
        "\x1bV410\x1bH40\x1bL0101\x1bXM456 Commerce Blvd"
        "\x1bV450\x1bH40\x1bL0101\x1bXMNew York, NY 10001"
        "\x1bV520\x1bH20\x1bFW0202H760"
        "\x1bV560\x1bH40\x1bL0101\x1bXMPO: 98765   SKU: A100"
        "\x1bV620\x1bH40\x1bL0101\x1bXMQTY: 50   WT: 25.5 LBS"
        "\x1bV700\x1bH20\x1bFW0202H760"
        "\x1bV750\x1bH100\x1bB103200*9876543210*"
        "\x1bV980\x1bH150\x1bL0101\x1bXM*9876543210*"
        "\x1bQ1"
        "\x1bZ"
    ),
}


class TestInputDialog(QDialog):
    """Dialog for entering SBPL data manually for testing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Test SBPL Input")
        self.setMinimumSize(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Sample selector
        sample_layout = QHBoxLayout()
        sample_layout.addWidget(QLabel("Load Sample:"))
        self.sample_combo = QComboBox()
        self.sample_combo.addItem("-- Select a sample --")
        for name in SAMPLES:
            self.sample_combo.addItem(name)
        self.sample_combo.currentTextChanged.connect(self._load_sample)
        sample_layout.addWidget(self.sample_combo)
        layout.addLayout(sample_layout)

        # Input area
        input_group = QGroupBox("SBPL Data (use \\x1b for ESC character)")
        input_layout = QVBoxLayout(input_group)

        self.input_edit = QTextEdit()
        self.input_edit.setFont(QFont("Courier New", 10))
        self.input_edit.setPlaceholderText(
            "Enter SBPL commands here.\n"
            "Use \\x1b for ESC (0x1B) character.\n"
            "Example:\n"
            "\\x1bA\n"
            "\\x1bV100\\x1bH50\\x1bL0202\\x1bXMHello World\n"
            "\\x1bQ1\n"
            "\\x1bZ"
        )
        input_layout.addWidget(self.input_edit)

        info = QLabel(
            "<i>ESC character: Use \\x1b or the literal ESC byte. "
            "Commands start with ESC followed by the command letter(s).</i>"
        )
        info.setWordWrap(True)
        input_layout.addWidget(info)
        layout.addWidget(input_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_sample(self, name: str):
        if name in SAMPLES:
            # Convert to displayable escaped format
            raw = SAMPLES[name]
            display = raw.replace("\x1b", "\\x1b").replace("\x02", "\\x02").replace("\x03", "\\x03")
            self.input_edit.setText(display)

    def get_sbpl_data(self) -> bytes:
        """Get the SBPL data as bytes."""
        text = self.input_edit.toPlainText()
        # Process escape sequences
        text = text.replace("\\x1b", "\x1b")
        text = text.replace("\\x1B", "\x1b")
        text = text.replace("\\x02", "\x02")
        text = text.replace("\\x03", "\x03")
        text = text.replace("\\r", "\r")
        text = text.replace("\\n", "\n")
        return text.encode("latin-1", errors="replace")
