"""
Rotation path generators — each returns (azimuth_deg, elevation_deg) at any time.

Formulas follow the ROADMAP exactly.
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from typing import Dict, Tuple, Type


class RotationPath(ABC):
    @abstractmethod
    def get_angle(self, time_s: float) -> Tuple[float, float]:
        """Return (azimuth_deg, elevation_deg)."""


class CirclePath(RotationPath):
    """Constant-speed horizontal circle at elevation 0."""

    def __init__(self, speed_hz: float = 0.15, clockwise: bool = True) -> None:
        self.speed_hz = speed_hz
        self._dir = 1.0 if clockwise else -1.0

    def get_angle(self, time_s: float) -> Tuple[float, float]:
        return (time_s * self.speed_hz * 360.0 * self._dir) % 360.0, 0.0


class Figure8Path(RotationPath):
    """Lissajous figure-8 mapped to azimuth/elevation."""

    def __init__(self, speed_hz: float = 0.15) -> None:
        self.speed_hz = speed_hz

    def get_angle(self, time_s: float) -> Tuple[float, float]:
        az = 90.0 * math.sin(2 * math.pi * self.speed_hz * time_s)
        el = 45.0 * math.sin(4 * math.pi * self.speed_hz * time_s)
        return az % 360.0, el


class SpiralPath(RotationPath):
    """Circle with slow elevation oscillation."""

    def __init__(self, speed_hz: float = 0.15, inward: bool = False) -> None:
        self.speed_hz = speed_hz
        self._sign = -1.0 if inward else 1.0

    def get_angle(self, time_s: float) -> Tuple[float, float]:
        az = (time_s * self.speed_hz * 360.0) % 360.0
        el = self._sign * 30.0 * math.sin(2 * math.pi * 0.1 * time_s)
        return az, el


class ElevationSweepPath(RotationPath):
    """Circle combined with full elevation range sweep."""

    def __init__(self, speed_hz: float = 0.15) -> None:
        self.speed_hz = speed_hz

    def get_angle(self, time_s: float) -> Tuple[float, float]:
        az = (time_s * self.speed_hz * 360.0) % 360.0
        el = 60.0 * math.sin(2 * math.pi * self.speed_hz * 0.25 * time_s)
        return az, el


class RandomDriftPath(RotationPath):
    """Brownian motion — slow, smooth, unpredictable. Good for ambient."""

    def __init__(self, speed_hz: float = 0.15, seed: int = 42) -> None:
        self.speed_hz = speed_hz
        rng = random.Random(seed)

        fps = 10
        n = fps * 600  # 600 s of trajectory

        az_list, el_list = [0.0], [0.0]
        az_v = el_v = 0.0
        step = speed_hz * 36.0 / fps

        for _ in range(n - 1):
            az_v = az_v * 0.95 + rng.gauss(0, step)
            el_v = el_v * 0.95 + rng.gauss(0, step * 0.3)
            az_list.append(az_list[-1] + az_v)
            el_list.append(max(-35.0, min(80.0, el_list[-1] + el_v)))

        self._az = az_list
        self._el = el_list
        self._fps = fps

    def get_angle(self, time_s: float) -> Tuple[float, float]:
        idx = int(time_s * self._fps) % len(self._az)
        return self._az[idx] % 360.0, self._el[idx]


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

PATH_CLASSES: Dict[str, Type[RotationPath]] = {
    "circle":    CirclePath,
    "figure8":   Figure8Path,
    "spiral":    SpiralPath,
    "elevation": ElevationSweepPath,
    "random":    RandomDriftPath,
}

PATH_LABELS = ["Circle", "Figure-8", "Spiral", "Elevation Sweep", "Random Drift"]
PATH_KEYS   = ["circle", "figure8", "spiral", "elevation", "random"]


def make_path(key: str, speed_hz: float) -> RotationPath:
    cls = PATH_CLASSES.get(key, CirclePath)
    return cls(speed_hz=speed_hz)


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    paths = {
        "circle":    CirclePath(0.15),
        "figure8":   Figure8Path(0.15),
        "spiral":    SpiralPath(0.15),
        "elevation": ElevationSweepPath(0.15),
        "random":    RandomDriftPath(0.15),
    }
    print("Rotation path self-test:")
    for name, p in paths.items():
        samples = [p.get_angle(t) for t in (0, 1, 2, 5, 10)]
        az_vals = [f"{a:.1f}" for a, _ in samples]
        el_vals = [f"{e:.1f}" for _, e in samples]
        print(f"  {name:12s}  az={az_vals}  el={el_vals}")
    print("test_rotation: PASSED")
