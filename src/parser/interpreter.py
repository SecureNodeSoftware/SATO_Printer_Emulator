"""SBPL command interpreter - processes parsed commands into render instructions."""

from dataclasses import dataclass, field
from typing import Optional
from src.parser.tokenizer import SBPLCommand, SBPLJob


@dataclass
class RenderText:
    """Instruction to render text."""
    x: int  # horizontal position in dots
    y: int  # vertical position in dots
    text: str
    font: str  # font command name (XU, XS, XM, XB, XL, U, S, M, WB, WL, OA, OB)
    smoothing: bool = False
    enlarge_h: int = 1
    enlarge_v: int = 1
    rotation: int = 0  # 0, 90, 180, 270
    pitch: int = 2


@dataclass
class RenderBarcode:
    """Instruction to render a barcode."""
    x: int
    y: int
    barcode_type: str  # e.g., "CODE39", "CODE128", "EAN13", etc.
    data: str
    narrow_width: int = 2
    bar_height: int = 100
    ratio: str = "1:3"  # "1:2", "1:3", "2:5"
    rotation: int = 0
    show_text: bool = False
    text_position: str = "bottom"


@dataclass
class RenderFrame:
    """Instruction to render a frame or ruler line."""
    x: int
    y: int
    line_width_v: int = 2
    line_width_h: int = 2
    is_frame: bool = False
    # For ruler (line):
    direction: str = "H"  # H or V
    line_length: int = 100
    # For frame:
    frame_height: int = 0
    frame_width: int = 0


@dataclass
class RenderInversion:
    """Instruction to render a black/white inversion region."""
    x: int
    y: int
    width: int
    height: int


@dataclass
class RenderGraphic:
    """Instruction to render raw graphic data."""
    x: int
    y: int
    width_bytes: int
    height_rows: int
    data: bytes
    data_format: str = "H"  # H for hex, B for binary
    enlarge_h: int = 1
    enlarge_v: int = 1
    rotation: int = 0


@dataclass
class RenderOutlineText:
    """Instruction to render outline font text."""
    x: int
    y: int
    text: str
    font_type: str = "A"  # A=Helvetica Bold proportional, B=fixed
    width: int = 50
    height: int = 50
    style: int = 0
    rotation: int = 0
    pitch: int = 0
    enlarge_h: int = 1
    enlarge_v: int = 1


@dataclass
class RenderCGFont:
    """Instruction to render CG font text."""
    x: int
    y: int
    text: str
    font_type: str = "A"  # A=CG Times, B=CG Triumvirate
    font_style: int = 0  # 00=Normal, 01=Bold
    h_size: int = 50
    v_size: int = 50
    rotation: int = 0
    enlarge_h: int = 1
    enlarge_v: int = 1


# Maps barcode type code to name
BARCODE_TYPE_MAP = {
    "0": "NW7",
    "1": "CODE39",
    "2": "ITF",  # Interleaved 2 of 5
    "3": "EAN13",
    "4": "EAN8",
    "5": "I2OF5",  # Industrial 2 of 5
    "6": "MATRIX25",
    "A": "MSI",
    "C": "CODE93",
    "E": "UPCE",
    "G": "CODE128",
    "F": "BOOKLAND",
    "H": "UPCA",
    "I": "EAN128",
    "P": "POSTNET",
}


class SBPLInterpreter:
    """Interprets SBPL commands and produces render instructions."""

    # Map command names (including special characters) to handler method names
    _COMMAND_DISPATCH = {
        "A": "_cmd_A", "Z": "_cmd_Z", "Q": "_cmd_Q",
        "H": "_cmd_H", "V": "_cmd_V", "P": "_cmd_P",
        "L": "_cmd_L", "E": "_cmd_E",
        "%": "_cmd_percent_",
        "XU": "_cmd_XU", "XS": "_cmd_XS", "XM": "_cmd_XM",
        "XB": "_cmd_XB", "XL": "_cmd_XL",
        "U": "_cmd_U", "S": "_cmd_S", "M": "_cmd_M",
        "WB": "_cmd_WB", "WL": "_cmd_WL",
        "OA": "_cmd_OA", "OB": "_cmd_OB",
        "$": "_cmd_dollar_", "$=": "_cmd_dollar_eq_",
        "RD": "_cmd_RD",
        "B": "_cmd_B", "D": "_cmd_D", "BD": "_cmd_BD",
        "BG": "_cmd_BG", "BC": "_cmd_BC", "BI": "_cmd_BI", "BP": "_cmd_BP",
        "FW": "_cmd_FW", "(": "_cmd_lparen_", "G": "_cmd_G",
        "&": "_cmd_amp_", "/": "_cmd_slash_",
        "F": "_cmd_F", "A1": "_cmd_A1", "#E": "_cmd_hash_E",
        "CS": "_cmd_CS", "C": "_cmd_C",
    }

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset interpreter state (called at <A> or <Z>)."""
        self.h_pos = 0
        self.v_pos = 0
        self.enlarge_h = 1
        self.enlarge_v = 1
        self.rotation = 0
        self.pitch = 2
        self.line_pitch = 0
        self.outline_font_type = "A"
        self.outline_font_width = 50
        self.outline_font_height = 50
        self.outline_font_style = 0
        self.render_list = []
        self.form_overlay = None

    def interpret_job(self, job: SBPLJob) -> list:
        """Interpret a complete print job and return render instructions."""
        self.reset()
        self.render_list = []

        for cmd in job.commands:
            self._dispatch(cmd)

        return self.render_list

    def _dispatch(self, cmd: SBPLCommand):
        """Dispatch a command to its handler."""
        method_name = self._COMMAND_DISPATCH.get(cmd.command)
        if method_name:
            handler = getattr(self, method_name, None)
            if handler:
                handler(cmd)

    # --- Control Commands ---

    def _cmd_A(self, cmd: SBPLCommand):
        """Data send start."""
        pass  # State already reset or maintained

    def _cmd_Z(self, cmd: SBPLCommand):
        """Data send end - resets state."""
        self.h_pos = 0
        self.v_pos = 0
        self.enlarge_h = 1
        self.enlarge_v = 1
        self.rotation = 0
        self.pitch = 2

    def _cmd_Q(self, cmd: SBPLCommand):
        """Print quantity - handled at job level."""
        pass

    # --- Position Commands ---

    def _cmd_H(self, cmd: SBPLCommand):
        """Horizontal position."""
        try:
            self.h_pos = int(cmd.params.strip())
        except ValueError:
            pass

    def _cmd_V(self, cmd: SBPLCommand):
        """Vertical position."""
        try:
            self.v_pos = int(cmd.params.strip())
        except ValueError:
            pass

    def _cmd_P(self, cmd: SBPLCommand):
        """Character pitch."""
        try:
            self.pitch = int(cmd.params.strip())
        except ValueError:
            self.pitch = 2

    def _cmd_L(self, cmd: SBPLCommand):
        """Enlargement specification - format: aabb (hh vv)."""
        p = cmd.params.strip()
        if len(p) >= 4:
            try:
                self.enlarge_h = int(p[:2])
                self.enlarge_v = int(p[2:4])
                self.enlarge_h = max(1, min(12, self.enlarge_h))
                self.enlarge_v = max(1, min(12, self.enlarge_v))
            except ValueError:
                pass

    def _cmd_E(self, cmd: SBPLCommand):
        """Auto line feed specification."""
        p = cmd.params.strip()
        # Extract line pitch (first 1-3 digits)
        digits = ""
        for ch in p:
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits:
            try:
                self.line_pitch = int(digits)
            except ValueError:
                pass

    # --- Rotation ---

    def _cmd_percent_(self, cmd: SBPLCommand):
        """Rotation specification."""
        p = cmd.params.strip()
        if p and p[0].isdigit():
            r = int(p[0])
            self.rotation = {0: 0, 1: 90, 2: 180, 3: 270}.get(r, 0)

    # --- Font Commands ---

    def _add_text(self, font: str, params: str, has_smoothing: bool = False):
        """Common handler for font commands."""
        text = params
        smoothing = False

        if has_smoothing and len(params) > 0:
            smoothing = params[0] == '1'
            text = params[1:]

        self.render_list.append(RenderText(
            x=self.h_pos,
            y=self.v_pos,
            text=text,
            font=font,
            smoothing=smoothing,
            enlarge_h=self.enlarge_h,
            enlarge_v=self.enlarge_v,
            rotation=self.rotation,
            pitch=self.pitch,
        ))

    def _cmd_XU(self, cmd: SBPLCommand):
        self._add_text("XU", cmd.params)

    def _cmd_XS(self, cmd: SBPLCommand):
        self._add_text("XS", cmd.params)

    def _cmd_XM(self, cmd: SBPLCommand):
        self._add_text("XM", cmd.params)

    def _cmd_XB(self, cmd: SBPLCommand):
        self._add_text("XB", cmd.params, has_smoothing=True)

    def _cmd_XL(self, cmd: SBPLCommand):
        self._add_text("XL", cmd.params, has_smoothing=True)

    def _cmd_U(self, cmd: SBPLCommand):
        self._add_text("U", cmd.params)

    def _cmd_S(self, cmd: SBPLCommand):
        self._add_text("S", cmd.params)

    def _cmd_M(self, cmd: SBPLCommand):
        self._add_text("M", cmd.params)

    def _cmd_WB(self, cmd: SBPLCommand):
        self._add_text("WB", cmd.params, has_smoothing=True)

    def _cmd_WL(self, cmd: SBPLCommand):
        self._add_text("WL", cmd.params, has_smoothing=True)

    def _cmd_OA(self, cmd: SBPLCommand):
        self._add_text("OA", cmd.params)

    def _cmd_OB(self, cmd: SBPLCommand):
        self._add_text("OB", cmd.params)

    # --- Outline Font ---

    def _cmd_dollar_(self, cmd: SBPLCommand):
        """Outline font shape specification: <$>a, bbb, ccc, d"""
        p = cmd.params.strip()
        parts = [x.strip() for x in p.split(",")]
        if len(parts) >= 4:
            self.outline_font_type = parts[0] if parts[0] in ("A", "B") else "A"
            try:
                self.outline_font_width = int(parts[1])
            except ValueError:
                self.outline_font_width = 50
            try:
                self.outline_font_height = int(parts[2])
            except ValueError:
                self.outline_font_height = 50
            try:
                self.outline_font_style = int(parts[3])
            except ValueError:
                self.outline_font_style = 0

    def _cmd_dollar_eq_(self, cmd: SBPLCommand):
        """Outline font print specification: <$=>data"""
        self.render_list.append(RenderOutlineText(
            x=self.h_pos,
            y=self.v_pos,
            text=cmd.params,
            font_type=self.outline_font_type,
            width=self.outline_font_width,
            height=self.outline_font_height,
            style=self.outline_font_style,
            rotation=self.rotation,
            pitch=self.pitch,
            enlarge_h=self.enlarge_h,
            enlarge_v=self.enlarge_v,
        ))

    # --- CG Font ---

    def _cmd_RD(self, cmd: SBPLCommand):
        """CG Font specification: <RD>abb, ccc, ddd, data"""
        p = cmd.params.strip()
        parts = [x.strip() for x in p.split(",")]
        if len(parts) >= 4:
            font_type = parts[0][0] if len(parts[0]) > 0 else "A"
            try:
                font_style = int(parts[0][1:3]) if len(parts[0]) >= 3 else 0
            except ValueError:
                font_style = 0
            h_size = self._parse_cg_size(parts[1])
            v_size = self._parse_cg_size(parts[2])
            text = ",".join(parts[3:])  # data may contain commas
            self.render_list.append(RenderCGFont(
                x=self.h_pos,
                y=self.v_pos,
                text=text.strip(),
                font_type=font_type,
                font_style=font_style,
                h_size=h_size,
                v_size=v_size,
                rotation=self.rotation,
                enlarge_h=self.enlarge_h,
                enlarge_v=self.enlarge_v,
            ))

    def _parse_cg_size(self, s: str) -> int:
        """Parse CG font size (dot or point specification)."""
        s = s.strip()
        if s.upper().startswith("P"):
            try:
                points = int(s[1:])
                return int(points * 0.35 * 8)  # approx conversion
            except ValueError:
                return 50
        try:
            return int(s)
        except ValueError:
            return 50

    # --- Barcode Commands ---

    def _parse_barcode_b(self, params: str, ratio: str):
        """Parse <B>, <D>, or <BD> barcode: abbcccdata"""
        p = params.strip()
        if len(p) < 6:
            return
        bc_type_code = p[0]
        bc_type = BARCODE_TYPE_MAP.get(bc_type_code, "CODE39")
        try:
            narrow_width = int(p[1:3])
            bar_height = int(p[3:6])
        except ValueError:
            return
        data = p[6:]
        self.render_list.append(RenderBarcode(
            x=self.h_pos,
            y=self.v_pos,
            barcode_type=bc_type,
            data=data,
            narrow_width=narrow_width,
            bar_height=bar_height,
            ratio=ratio,
            rotation=self.rotation,
        ))

    def _cmd_B(self, cmd: SBPLCommand):
        """Barcode 1:3 ratio."""
        self._parse_barcode_b(cmd.params, "1:3")

    def _cmd_D(self, cmd: SBPLCommand):
        """Barcode 1:2 ratio."""
        self._parse_barcode_b(cmd.params, "1:2")

    def _cmd_BD(self, cmd: SBPLCommand):
        """Barcode 2:5 ratio."""
        self._parse_barcode_b(cmd.params, "2:5")

    def _cmd_BG(self, cmd: SBPLCommand):
        """CODE128 barcode: aabbbnnn"""
        p = cmd.params.strip()
        if len(p) < 5:
            return
        try:
            narrow_width = int(p[0:2])
            bar_height = int(p[2:5])
        except ValueError:
            return
        data = p[5:]
        self.render_list.append(RenderBarcode(
            x=self.h_pos,
            y=self.v_pos,
            barcode_type="CODE128",
            data=data,
            narrow_width=narrow_width,
            bar_height=bar_height,
            rotation=self.rotation,
        ))

    def _cmd_BC(self, cmd: SBPLCommand):
        """CODE93 barcode: aabbbccdata"""
        p = cmd.params.strip()
        if len(p) < 7:
            return
        try:
            narrow_width = int(p[0:2])
            bar_height = int(p[2:5])
            data_digits = int(p[5:7])
        except ValueError:
            return
        data = p[7:7 + data_digits]
        self.render_list.append(RenderBarcode(
            x=self.h_pos,
            y=self.v_pos,
            barcode_type="CODE93",
            data=data,
            narrow_width=narrow_width,
            bar_height=bar_height,
            rotation=self.rotation,
        ))

    def _cmd_BI(self, cmd: SBPLCommand):
        """UCC/EAN-128 barcode: aabbbcdata"""
        p = cmd.params.strip()
        if len(p) < 6:
            return
        try:
            narrow_width = int(p[0:2])
            bar_height = int(p[2:5])
        except ValueError:
            return
        show_text_code = p[5] if len(p) > 5 else "0"
        data = p[6:]
        self.render_list.append(RenderBarcode(
            x=self.h_pos,
            y=self.v_pos,
            barcode_type="EAN128",
            data=data,
            narrow_width=narrow_width,
            bar_height=bar_height,
            rotation=self.rotation,
            show_text=show_text_code in ("1", "2"),
            text_position="top" if show_text_code == "1" else "bottom",
        ))

    def _cmd_BP(self, cmd: SBPLCommand):
        """POSTNET barcode."""
        data = cmd.params.strip()
        self.render_list.append(RenderBarcode(
            x=self.h_pos,
            y=self.v_pos,
            barcode_type="POSTNET",
            data=data,
            rotation=self.rotation,
        ))

    # --- Graphics ---

    def _cmd_FW(self, cmd: SBPLCommand):
        """Frame/ruler specification."""
        p = cmd.params.strip()

        # Check if it's a frame (contains both V and H after initial width params)
        if 'V' in p[2:] and 'H' in p[2:]:
            # Frame: aabbVccccHdddd
            try:
                lw_v = int(p[0:2])
                lw_h = int(p[2:4])
                rest = p[4:]
                # Parse VxxxxHxxxx
                v_match = rest.split('V')[1] if 'V' in rest else ""
                parts = v_match.split('H')
                frame_h = int(parts[0]) if parts[0] else 0
                frame_w = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                self.render_list.append(RenderFrame(
                    x=self.h_pos,
                    y=self.v_pos,
                    line_width_v=lw_v,
                    line_width_h=lw_h,
                    is_frame=True,
                    frame_height=frame_h,
                    frame_width=frame_w,
                ))
            except (ValueError, IndexError):
                pass
        else:
            # Ruler line: aabcccc
            try:
                lw = int(p[0:2])
                direction = ""
                length = 0
                rest = p[2:]
                if rest.startswith("H"):
                    direction = "H"
                    length = int(rest[1:])
                elif rest.startswith("V"):
                    direction = "V"
                    length = int(rest[1:])
                self.render_list.append(RenderFrame(
                    x=self.h_pos,
                    y=self.v_pos,
                    line_width_v=lw,
                    line_width_h=lw,
                    is_frame=False,
                    direction=direction,
                    line_length=length,
                ))
            except (ValueError, IndexError):
                pass

    def _cmd_lparen_(self, cmd: SBPLCommand):
        """Black/white inversion: aaaa, bbbb"""
        p = cmd.params.strip()
        parts = [x.strip() for x in p.split(",")]
        if len(parts) >= 2:
            try:
                width = int(parts[0])
                height = int(parts[1])
                self.render_list.append(RenderInversion(
                    x=self.h_pos,
                    y=self.v_pos,
                    width=width,
                    height=height,
                ))
            except ValueError:
                pass

    def _cmd_G(self, cmd: SBPLCommand):
        """Graphic data: abbbcccdata"""
        p = cmd.params
        if len(p) < 7:
            return
        data_format = p[0].upper()
        try:
            width_bytes = int(p[1:4])
            height_rows = int(p[4:7])
        except ValueError:
            return
        graphic_data = p[7:]
        if data_format == "H":
            # Convert hex string to bytes
            try:
                raw = bytes.fromhex(graphic_data.replace(" ", ""))
            except ValueError:
                raw = b""
        else:
            raw = graphic_data.encode('latin-1')
        self.render_list.append(RenderGraphic(
            x=self.h_pos,
            y=self.v_pos,
            width_bytes=width_bytes,
            height_rows=height_rows,
            data=raw,
            data_format=data_format,
            enlarge_h=self.enlarge_h,
            enlarge_v=self.enlarge_v,
            rotation=self.rotation,
        ))

    # --- Form Overlay ---

    def _cmd_amp_(self, cmd: SBPLCommand):
        """Register form overlay - save current render list."""
        self.form_overlay = list(self.render_list)

    def _cmd_slash_(self, cmd: SBPLCommand):
        """Call form overlay - prepend saved render list."""
        if self.form_overlay:
            self.render_list = list(self.form_overlay) + self.render_list

    # --- Sequential Number ---

    def _cmd_F(self, cmd: SBPLCommand):
        """Sequential number - store params for next data command."""
        # For emulation, we just pass through; sequential numbering is mostly
        # relevant for multi-label runs
        pass

    # --- System Commands (informational, affect emulator settings) ---

    def _cmd_A1(self, cmd: SBPLCommand):
        """Label size specification - stored for reference."""
        pass

    def _cmd_hash_E(self, cmd: SBPLCommand):
        """Print density specification."""
        pass

    def _cmd_CS(self, cmd: SBPLCommand):
        """Print speed specification."""
        pass

    def _cmd_C(self, cmd: SBPLCommand):
        """Clear specification."""
        self.reset()
        self.render_list = []
