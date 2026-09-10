from output_styles import (
    DEFAULT_HEATMAP_COLORS,
    apply_output_preset,
    color_at,
    hex_to_rgb,
    normalize_hex,
)


def test_hex_normalization():
    assert normalize_hex("1450ff", "#000000") == "#1450FF"
    assert normalize_hex("bad", "#123456") == "#123456"
    assert hex_to_rgb("#FF8000") == (255, 128, 0)


def test_heatmap_endpoints():
    assert color_at(0.0, DEFAULT_HEATMAP_COLORS) == hex_to_rgb(DEFAULT_HEATMAP_COLORS[0])
    assert color_at(1.0, DEFAULT_HEATMAP_COLORS) == hex_to_rgb(DEFAULT_HEATMAP_COLORS[-1])


def test_standard_preset_keeps_pins_separate():
    preset = apply_output_preset("Standard")
    assert preset["output_stations"] is True
    assert preset["output_network_heatmap"] is True
    assert preset["output_per_station_heatmaps"] is False


def test_station_analysis_uses_per_station_heatmaps():
    preset = apply_output_preset("Station Analysis")
    assert preset["output_stations"] is True
    assert preset["output_network_heatmap"] is False
    assert preset["output_per_station_heatmaps"] is True
