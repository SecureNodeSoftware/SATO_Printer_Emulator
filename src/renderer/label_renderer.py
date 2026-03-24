"""Label rendering engine - converts render instructions to bitmap images."""

import io
import math
from PIL import Image, ImageChops, ImageDraw, ImageFont
from typing import Optional

from src.config.settings import PrinterConfig
from src.fonts.bitmap_fonts import get_font_metrics
from src.parser.interpreter import (
    RenderText, RenderBarcode, RenderFrame, RenderInversion,
    RenderGraphic, RenderOutlineText, RenderCGFont,
)


class LabelRenderer:
    """Renders SBPL instructions onto a Pillow Image."""

    def __init__(self, config: PrinterConfig):
        self.config = config
        self.width = config.label_width_dots
        self.height = config.label_height_dots
        self.image: Optional[Image.Image] = None
        self.draw: Optional[ImageDraw.ImageDraw] = None
        self._font_cache = {}

    def create_canvas(self):
        """Create a blank white label canvas."""
        self.image = Image.new("1", (self.width, self.height), 1)  # 1-bit, white
        self.draw = ImageDraw.Draw(self.image)

    def render(self, instructions: list) -> Image.Image:
        """Render a list of instructions and return the resulting image."""
        self.create_canvas()

        for instr in instructions:
            if isinstance(instr, RenderText):
                self._render_text(instr)
            elif isinstance(instr, RenderBarcode):
                self._render_barcode(instr)
            elif isinstance(instr, RenderFrame):
                self._render_frame(instr)
            elif isinstance(instr, RenderInversion):
                self._render_inversion(instr)
            elif isinstance(instr, RenderGraphic):
                self._render_graphic(instr)
            elif isinstance(instr, RenderOutlineText):
                self._render_outline_text(instr)
            elif isinstance(instr, RenderCGFont):
                self._render_cg_font(instr)

        return self.image

    def _get_bitmap_font(self, font_name: str, enlarge_h: int, enlarge_v: int) -> ImageFont.FreeTypeFont:
        """Get or create a scaled font for rendering."""
        metrics = get_font_metrics(font_name, self.config.dpi)
        # Target pixel height = base_height * enlarge_v
        target_height = metrics.base_height * enlarge_v
        cache_key = (font_name, target_height)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # Use Pillow's default font scaled to approximate the target
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", target_height)
        except (IOError, OSError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", target_height)
            except (IOError, OSError):
                try:
                    font = ImageFont.truetype("cour.ttf", target_height)
                except (IOError, OSError):
                    font = ImageFont.load_default()

        self._font_cache[cache_key] = font
        return font

    def _get_outline_font(self, width: int, height: int, font_type: str) -> ImageFont.FreeTypeFont:
        """Get font for outline text rendering."""
        cache_key = ("outline", font_type, height)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        if font_type == "B":  # Fixed pitch
            font_names = ["DejaVuSansMono-Bold.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                          "courbd.ttf"]
        else:  # Proportional (Helvetica Bold equivalent)
            font_names = ["DejaVuSans-Bold.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                          "arialbd.ttf"]

        font = None
        for name in font_names:
            try:
                font = ImageFont.truetype(name, height)
                break
            except (IOError, OSError):
                continue

        if font is None:
            font = ImageFont.load_default()

        self._font_cache[cache_key] = font
        return font

    def _render_text(self, instr: RenderText):
        """Render bitmap font text."""
        if not instr.text:
            return

        metrics = get_font_metrics(instr.font, self.config.dpi)
        font = self._get_bitmap_font(instr.font, instr.enlarge_h, instr.enlarge_v)

        char_width = metrics.base_width * instr.enlarge_h
        char_height = metrics.base_height * instr.enlarge_v
        pitch = instr.pitch * instr.enlarge_h

        if instr.rotation == 0:
            # Render each character at position
            x = instr.x
            y = instr.y
            for ch in instr.text:
                self._draw_char(ch, x, y, font, char_width, char_height,
                                instr.enlarge_h, instr.enlarge_v, 0)
                x += char_width + pitch
        else:
            self._render_rotated_text(instr, font, char_width, char_height, pitch, metrics)

    def _render_rotated_text(self, instr: RenderText, font, char_width, char_height, pitch, metrics):
        """Render text with rotation."""
        # Render text to a temporary image, then rotate and paste
        total_width = len(instr.text) * (char_width + pitch) - pitch
        if total_width <= 0 or char_height <= 0:
            return

        tmp = Image.new("1", (total_width, char_height), 1)
        tmp_draw = ImageDraw.Draw(tmp)
        x = 0
        for ch in instr.text:
            tmp_draw.text((x, 0), ch, font=font, fill=0)
            x += char_width + pitch

        # Rotate
        if instr.rotation == 90:
            tmp = tmp.transpose(Image.Transpose.ROTATE_90)
        elif instr.rotation == 180:
            tmp = tmp.transpose(Image.Transpose.ROTATE_180)
        elif instr.rotation == 270:
            tmp = tmp.transpose(Image.Transpose.ROTATE_270)

        self._paste_1bit(tmp, instr.x, instr.y)

    def _draw_char(self, ch: str, x: int, y: int, font, char_width: int, char_height: int,
                   enlarge_h: int, enlarge_v: int, rotation: int):
        """Draw a single character."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        self.draw.text((x, y), ch, font=font, fill=0)

    def _render_barcode(self, instr: RenderBarcode):
        """Render a barcode."""
        try:
            barcode_img = self._generate_barcode_image(instr)
            if barcode_img:
                if instr.rotation != 0:
                    if instr.rotation == 90:
                        barcode_img = barcode_img.transpose(Image.Transpose.ROTATE_90)
                    elif instr.rotation == 180:
                        barcode_img = barcode_img.transpose(Image.Transpose.ROTATE_180)
                    elif instr.rotation == 270:
                        barcode_img = barcode_img.transpose(Image.Transpose.ROTATE_270)
                self._paste_1bit(barcode_img, instr.x, instr.y)
        except Exception:
            # If barcode generation fails, render placeholder
            self._render_barcode_fallback(instr)

    def _generate_barcode_image(self, instr: RenderBarcode) -> Optional[Image.Image]:
        """Generate a barcode image using python-barcode."""
        import barcode as barcode_lib
        from barcode.writer import ImageWriter

        data = instr.data.strip().strip("*")
        bc_type = instr.barcode_type

        # Map SBPL type to python-barcode type
        type_map = {
            "CODE39": "code39",
            "CODE128": "code128",
            "EAN13": "ean13",
            "EAN8": "ean8",
            "UPCA": "upca",
            "UPCE": "upce",
            "ITF": "itf",
            "NW7": "codabar",  # Not directly supported, use code39 as fallback
        }

        bc_name = type_map.get(bc_type)

        # Fallback for unsupported types - render as CODE128
        if bc_name is None:
            bc_name = "code128"

        # Validate data length for specific types
        if bc_name == "ean13" and len(data) not in (12, 13):
            bc_name = "code128"
        elif bc_name == "ean8" and len(data) not in (7, 8):
            bc_name = "code128"
        elif bc_name == "upca" and len(data) not in (11, 12):
            bc_name = "code128"

        try:
            writer = ImageWriter()
            bc = barcode_lib.get(bc_name, data, writer)
            # Configure writer options
            options = {
                "module_width": max(0.2, instr.narrow_width * 0.1),
                "module_height": max(5, instr.bar_height * 0.125),
                "write_text": instr.show_text,
                "quiet_zone": 2,
                "font_size": 8 if instr.show_text else 0,
            }
            buffer = io.BytesIO()
            bc.write(buffer, options=options)
            buffer.seek(0)
            img = Image.open(buffer).convert("1")
            img.load()  # Ensure pixel data is read before buffer may be garbage collected
            return img
        except Exception:
            return None

    def _render_barcode_fallback(self, instr: RenderBarcode):
        """Render a simple barcode placeholder when generation fails."""
        data = instr.data.strip().strip("*")
        # Draw alternating bars as a simple visual
        bar_x = instr.x
        narrow = max(1, instr.narrow_width)
        for i, ch in enumerate(data):
            val = ord(ch)
            for bit in range(4):
                if (val >> (3 - bit)) & 1:
                    width = narrow
                else:
                    width = narrow * 2
                if (i * 4 + bit) % 2 == 0:
                    self.draw.rectangle(
                        [bar_x, instr.y, bar_x + width - 1, instr.y + instr.bar_height],
                        fill=0
                    )
                bar_x += width

        # Draw data text below barcode
        try:
            font = self._get_bitmap_font("XS", 1, 1)
            self.draw.text((instr.x, instr.y + instr.bar_height + 2), data, font=font, fill=0)
        except Exception:
            pass

    def _render_frame(self, instr: RenderFrame):
        """Render a frame or ruler line."""
        if instr.is_frame:
            x1 = instr.x
            y1 = instr.y
            x2 = instr.x + instr.frame_width
            y2 = instr.y + instr.frame_height

            # Top line
            self.draw.rectangle([x1, y1, x2, y1 + instr.line_width_h - 1], fill=0)
            # Bottom line
            self.draw.rectangle([x1, y2 - instr.line_width_h + 1, x2, y2], fill=0)
            # Left line
            self.draw.rectangle([x1, y1, x1 + instr.line_width_v - 1, y2], fill=0)
            # Right line
            self.draw.rectangle([x2 - instr.line_width_v + 1, y1, x2, y2], fill=0)
        else:
            # Ruler line
            lw = instr.line_width_v
            if instr.direction == "H":
                self.draw.rectangle(
                    [instr.x, instr.y, instr.x + instr.line_length, instr.y + lw - 1],
                    fill=0
                )
            elif instr.direction == "V":
                self.draw.rectangle(
                    [instr.x, instr.y, instr.x + lw - 1, instr.y + instr.line_length],
                    fill=0
                )

    def _render_inversion(self, instr: RenderInversion):
        """Render black/white inversion region."""
        x1 = max(0, instr.x)
        y1 = max(0, instr.y)
        x2 = min(instr.x + instr.width, self.width)
        y2 = min(instr.y + instr.height, self.height)

        if x2 <= x1 or y2 <= y1:
            return

        # Crop, invert, and paste back
        region = self.image.crop((x1, y1, x2, y2))
        inverted = ImageChops.invert(region)
        self.image.paste(inverted, (x1, y1))

    def _render_graphic(self, instr: RenderGraphic):
        """Render raw graphic data."""
        data = instr.data
        if not data:
            return

        w_pixels = instr.width_bytes * 8
        h_pixels = instr.height_rows

        # Create graphic image from bitmap data
        graphic = Image.new("1", (w_pixels, h_pixels), 1)

        byte_idx = 0
        for row in range(h_pixels):
            for col_byte in range(instr.width_bytes):
                if byte_idx >= len(data):
                    break
                byte_val = data[byte_idx]
                for bit in range(8):
                    px = col_byte * 8 + bit
                    if px < w_pixels:
                        if byte_val & (0x80 >> bit):
                            graphic.putpixel((px, row), 0)
                byte_idx += 1

        # Apply enlargement
        if instr.enlarge_h > 1 or instr.enlarge_v > 1:
            new_w = w_pixels * instr.enlarge_h
            new_h = h_pixels * instr.enlarge_v
            graphic = graphic.resize((new_w, new_h), Image.Resampling.NEAREST)

        # Apply rotation
        if instr.rotation == 90:
            graphic = graphic.transpose(Image.Transpose.ROTATE_90)
        elif instr.rotation == 180:
            graphic = graphic.transpose(Image.Transpose.ROTATE_180)
        elif instr.rotation == 270:
            graphic = graphic.transpose(Image.Transpose.ROTATE_270)

        self._paste_1bit(graphic, instr.x, instr.y)

    def _render_outline_text(self, instr: RenderOutlineText):
        """Render outline font text."""
        if not instr.text:
            return

        height = instr.height * instr.enlarge_v
        width = instr.width * instr.enlarge_h
        font = self._get_outline_font(width, height, instr.font_type)

        if instr.rotation == 0:
            if instr.style == 0:
                # Standard black text
                self.draw.text((instr.x, instr.y), instr.text, font=font, fill=0)
            elif instr.style == 1:
                # Inversion (white on black box)
                bbox = font.getbbox(instr.text)
                tw = bbox[2] - bbox[0] + 4
                th = bbox[3] - bbox[1] + 4
                self.draw.rectangle(
                    [instr.x, instr.y, instr.x + tw, instr.y + th], fill=0
                )
                self.draw.text((instr.x + 2, instr.y + 2), instr.text, font=font, fill=1)
            elif instr.style in (2, 3, 4):
                # Gray patterns - approximate with dithered text
                self.draw.text((instr.x, instr.y), instr.text, font=font, fill=0)
            elif instr.style == 5:
                # Shadow
                self.draw.text((instr.x + 2, instr.y + 2), instr.text, font=font, fill=0)
                self.draw.text((instr.x, instr.y), instr.text, font=font, fill=0)
            elif instr.style == 6:
                # Inversion with shadow
                bbox = font.getbbox(instr.text)
                tw = bbox[2] - bbox[0] + 4
                th = bbox[3] - bbox[1] + 4
                self.draw.rectangle(
                    [instr.x + 2, instr.y + 2, instr.x + tw + 2, instr.y + th + 2], fill=0
                )
                self.draw.rectangle(
                    [instr.x, instr.y, instr.x + tw, instr.y + th], fill=0
                )
                self.draw.text((instr.x + 2, instr.y + 2), instr.text, font=font, fill=1)
            else:
                self.draw.text((instr.x, instr.y), instr.text, font=font, fill=0)
        else:
            # Rotated outline text
            bbox = font.getbbox(instr.text)
            tw = bbox[2] - bbox[0] + 4
            th = bbox[3] - bbox[1] + 4
            if tw <= 0 or th <= 0:
                return
            tmp = Image.new("1", (tw, th), 1)
            tmp_draw = ImageDraw.Draw(tmp)
            tmp_draw.text((2, 2), instr.text, font=font, fill=0)
            if instr.rotation == 90:
                tmp = tmp.transpose(Image.Transpose.ROTATE_90)
            elif instr.rotation == 180:
                tmp = tmp.transpose(Image.Transpose.ROTATE_180)
            elif instr.rotation == 270:
                tmp = tmp.transpose(Image.Transpose.ROTATE_270)
            self._paste_1bit(tmp, instr.x, instr.y)

    def _render_cg_font(self, instr: RenderCGFont):
        """Render CG font text."""
        if not instr.text:
            return

        height = instr.v_size * instr.enlarge_v
        font = self._get_outline_font(instr.h_size, height, "A" if instr.font_type == "A" else "B")

        if instr.rotation == 0:
            self.draw.text((instr.x, instr.y), instr.text, font=font, fill=0)
        else:
            bbox = font.getbbox(instr.text)
            tw = bbox[2] - bbox[0] + 4
            th = bbox[3] - bbox[1] + 4
            if tw <= 0 or th <= 0:
                return
            tmp = Image.new("1", (tw, th), 1)
            tmp_draw = ImageDraw.Draw(tmp)
            tmp_draw.text((2, 2), instr.text, font=font, fill=0)
            if instr.rotation == 90:
                tmp = tmp.transpose(Image.Transpose.ROTATE_90)
            elif instr.rotation == 180:
                tmp = tmp.transpose(Image.Transpose.ROTATE_180)
            elif instr.rotation == 270:
                tmp = tmp.transpose(Image.Transpose.ROTATE_270)
            self._paste_1bit(tmp, instr.x, instr.y)

    def _paste_1bit(self, src: Image.Image, x: int, y: int):
        """Paste a 1-bit image onto the canvas, merging black pixels."""
        if x >= self.width or y >= self.height:
            return

        src_w, src_h = src.size
        # Crop to fit within canvas
        crop_right = min(src_w, self.width - x)
        crop_bottom = min(src_h, self.height - y)
        paste_x = max(0, x)
        paste_y = max(0, y)
        src_x = max(0, -x)
        src_y = max(0, -y)

        if crop_right <= src_x or crop_bottom <= src_y:
            return

        cropped = src.crop((src_x, src_y, crop_right, crop_bottom))
        # Merge: if src pixel is black (0), dest becomes black
        # In 1-bit mode, multiply = AND: both must be white (1) to stay white
        region = self.image.crop((paste_x, paste_y,
                                   paste_x + cropped.width,
                                   paste_y + cropped.height))
        merged = ImageChops.multiply(region, cropped)
        self.image.paste(merged, (paste_x, paste_y))

    def get_display_image(self) -> Image.Image:
        """Get the label image converted to RGB for display."""
        if self.image is None:
            self.create_canvas()
        return self.image.convert("RGB")

    def save_png(self, filepath: str, dpi: int = None):
        """Save the current label as a PNG file."""
        if self.image is None:
            return
        if dpi is None:
            dpi = self.config.dpi
        # Convert to grayscale for better PNG output
        output = self.image.convert("L")
        output.save(filepath, "PNG", dpi=(dpi, dpi))
