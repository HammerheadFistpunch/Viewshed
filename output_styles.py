from __future__ import annotations

DEFAULT_HEATMAP_COLORS = (
    "#1450FF",
    "#14FFFF",
    "#14FF50",
    "#FFFF00",
    "#FF8800",
    "#FF0000",
)
DEFAULT_POSITIVE_COLOR = "#20C85A"
DEFAULT_GAP_COLOR = "#DC2323"
DEFAULT_REDUNDANCY_COLORS = ("#FFD54F", "#FF9800", "#E53935")


def normalize_hex(value: str, fallback: str) -> str:
    text = str(value or "").strip().upper()
    if not text.startswith("#"):
        text = "#" + text
    if len(text) != 7:
        return fallback
    try:
        int(text[1:], 16)
    except ValueError:
        return fallback
    return text


def hex_to_rgb(value: str, fallback: str = "#FFFFFF") -> tuple[int, int, int]:
    value = normalize_hex(value, fallback)
    return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))


def heatmap_colors(cfg: dict) -> tuple[str, ...]:
    raw = cfg.get("heatmap_colors")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        colors = tuple(normalize_hex(v, DEFAULT_HEATMAP_COLORS[min(i, len(DEFAULT_HEATMAP_COLORS) - 1)]) for i, v in enumerate(raw[:6]))
        if len(colors) >= 2:
            return colors
    return DEFAULT_HEATMAP_COLORS


def color_at(norm: float, colors: tuple[str, ...]) -> tuple[int, int, int]:
    norm = max(0.0, min(1.0, float(norm)))
    if len(colors) == 1:
        return hex_to_rgb(colors[0])
    pos = norm * (len(colors) - 1)
    lo = int(pos)
    hi = min(len(colors) - 1, lo + 1)
    t = pos - lo
    a = hex_to_rgb(colors[lo])
    b = hex_to_rgb(colors[hi])
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def heatmap_rgba(data, cfg: dict, *, nodata: float = -1.0):
    import numpy as np

    d = np.asarray(data, dtype=np.float32)
    rgba = np.zeros((*d.shape, 4), dtype=np.uint8)
    valid = np.isfinite(d) & (d > nodata) & (d >= 0.0)
    if not np.any(valid):
        return rgba

    band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
    max_db = max(band_db, float(cfg.get("max_margin_db", 30.0)))
    banded = np.floor(np.clip(d[valid], 0.0, max_db) / band_db) * band_db
    norms = np.clip(banded / max_db, 0.0, 1.0)
    colors = heatmap_colors(cfg)
    rgb = np.array([color_at(v, colors) for v in norms], dtype=np.uint8)
    rgba[valid, :3] = rgb
    rgba[valid, 3] = int(cfg.get("overlay_alpha", 180))
    return rgba


def solid_mask_rgba(mask, color: str, alpha: int):
    import numpy as np

    m = np.asarray(mask, dtype=bool)
    rgba = np.zeros((*m.shape, 4), dtype=np.uint8)
    rgb = hex_to_rgb(color)
    rgba[m, 0] = rgb[0]
    rgba[m, 1] = rgb[1]
    rgba[m, 2] = rgb[2]
    rgba[m, 3] = max(0, min(255, int(alpha)))
    return rgba


def redundancy_rgba(counts, cfg: dict):
    import numpy as np

    data = np.asarray(counts)
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    colors = cfg.get("redundancy_colors") or DEFAULT_REDUNDANCY_COLORS
    colors = tuple(normalize_hex(v, DEFAULT_REDUNDANCY_COLORS[min(i, 2)]) for i, v in enumerate(colors[:3]))
    alpha = int(cfg.get("overlay_alpha", 180))
    for selector, color in ((data == 1, colors[0]), (data == 2, colors[1]), (data >= 3, colors[2])):
        rgb = hex_to_rgb(color)
        rgba[selector, 0] = rgb[0]
        rgba[selector, 1] = rgb[1]
        rgba[selector, 2] = rgb[2]
        rgba[selector, 3] = alpha
    return rgba


def apply_output_preset(name: str) -> dict[str, bool]:
    presets = {
        "Standard": dict(output_stations=True, output_network_heatmap=True, output_positive=False, output_gaps=False, output_redundancy=False, output_per_station_heatmaps=False),
        "Coverage Analysis": dict(output_stations=True, output_network_heatmap=True, output_positive=True, output_gaps=True, output_redundancy=True, output_per_station_heatmaps=False),
        "Station Analysis": dict(output_stations=True, output_network_heatmap=False, output_positive=False, output_gaps=False, output_redundancy=False, output_per_station_heatmaps=True),
        "Everything": dict(output_stations=True, output_network_heatmap=True, output_positive=True, output_gaps=True, output_redundancy=True, output_per_station_heatmaps=True),
    }
    return presets.get(name, {})
