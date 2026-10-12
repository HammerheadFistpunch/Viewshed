"""Terrain and loss sampling for microwave coverage maps."""
import math
import numpy as np


def microwave_distances(distance_m, pixel_size_m, spacing_m):
    # Never imply finer accuracy than the working DEM. Include the near field
    # and exact far endpoint; limit CPU cost visibly rather than silently thinning.
    spacing = max(float(pixel_size_m), float(spacing_m))
    count = max(2, math.ceil(distance_m / spacing) + 1)
    if count > 4096:
        raise ValueError("Microwave run exceeds 4096 loss samples per radial; reduce radius or increase sample spacing.")
    distances = np.linspace(min(distance_m, pixel_size_m), distance_m, count)
    # Include the boundary where the near-field estimate switches to ITM.
    if distances[0] < 1000.0 < distance_m:
        distances = np.unique(np.append(distances, 1000.0))
    return distances


def profile_to_distance(profile, total_distance_m, target_distance_m):
    """Preserve uniform profile spacing and interpolate the exact endpoint."""
    fraction = min(1.0, max(0.0, target_distance_m / total_distance_m))
    count = max(2, math.ceil(fraction * (len(profile) - 1)) + 1)
    source = np.linspace(0.0, total_distance_m, len(profile))
    target = np.linspace(0.0, target_distance_m, count)
    return np.interp(target, source, profile).tolist()
