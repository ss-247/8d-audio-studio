"""Tests for engine/spatial/rotation.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.spatial.rotation import (
    CirclePath, Figure8Path, SpiralPath,
    ElevationSweepPath, RandomDriftPath, make_path, PATH_KEYS,
)


def test_circle_azimuth_range():
    p = CirclePath(speed_hz=1.0)
    for t in range(100):
        az, el = p.get_angle(t * 0.1)
        assert 0.0 <= az < 360.0, f"az={az} out of range"
        assert el == 0.0, f"CirclePath elevation should be 0, got {el}"


def test_circle_full_rotation():
    """At speed=1 Hz, exactly one full circle in 1 second."""
    p = CirclePath(speed_hz=1.0)
    az0, _ = p.get_angle(0.0)
    az1, _ = p.get_angle(1.0)
    assert abs((az1 - az0) % 360.0) < 0.01, "Should complete one rotation in 1s"


def test_elevation_bounds():
    for cls in [Figure8Path, SpiralPath, ElevationSweepPath, RandomDriftPath]:
        p = cls(speed_hz=0.2)
        for t in range(200):
            _, el = p.get_angle(t * 0.5)
            assert -90.0 <= el <= 90.0, f"{cls.__name__} el={el} out of [-90,90]"


def test_make_path():
    for key in PATH_KEYS:
        p = make_path(key, 0.15)
        az, el = p.get_angle(1.0)
        assert isinstance(az, float) and isinstance(el, float)


if __name__ == "__main__":
    for fn in [test_circle_azimuth_range, test_circle_full_rotation,
               test_elevation_bounds, test_make_path]:
        print(f"Running {fn.__name__}...")
        fn()
        print(f"  PASSED")
    print("test_rotation: ALL PASSED")
