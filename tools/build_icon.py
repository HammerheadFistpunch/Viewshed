from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / "assets" / "signal-peak-icon.svg"
OUTPUT_DIR = ROOT / "build"
ICO_PATH = OUTPUT_DIR / "signal_peak.ico"
CANVAS = 256
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _hex_rgba(value: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Unsupported SVG color: {value}")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b, max(0, min(255, round(255 * opacity)))


def _float(element: ET.Element, name: str, default: float = 0.0) -> float:
    return float(element.attrib.get(name, default))


def _points(value: str, scale: float) -> list[tuple[float, float]]:
    pairs = re.findall(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", value)
    return [(float(x) * scale, float(y) * scale) for x, y in pairs]


def main() -> None:
    tree = ET.parse(SVG_PATH)
    root = tree.getroot()
    view_box = [float(v) for v in root.attrib.get("viewBox", "0 0 32 32").split()]
    if len(view_box) != 4 or view_box[0] != 0 or view_box[1] != 0 or view_box[2] != view_box[3]:
        raise ValueError("Icon builder expects a square SVG viewBox starting at 0,0.")

    scale = CANVAS / view_box[2]
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    for element in root:
        tag = element.tag.rsplit("}", 1)[-1]
        fill = element.attrib.get("fill")
        if not fill or fill == "none":
            continue
        opacity = float(element.attrib.get("opacity", "1"))
        color = _hex_rgba(fill, opacity)

        if tag == "rect":
            x = _float(element, "x") * scale
            y = _float(element, "y") * scale
            width = _float(element, "width") * scale
            height = _float(element, "height") * scale
            radius = _float(element, "rx") * scale
            draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=color)
        elif tag == "polygon":
            draw.polygon(_points(element.attrib["points"], scale), fill=color)
        else:
            raise ValueError(f"Unsupported SVG element in Signal Peak icon: {tag}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(ICO_PATH, format="ICO", sizes=SIZES)
    print(f"Generated Windows icon: {ICO_PATH}")


if __name__ == "__main__":
    main()
