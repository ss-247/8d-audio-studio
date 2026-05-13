"""Tests for engine/spatial/binaural.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from engine.spatial.hrtf import HRTFDatabase
from engine.spatial.rotation import CirclePath, Figure8Path
from engine.spatial.binaural import BinauralProcessor

SOFA = Path(__file__).resolve().parents[1] / "data/hrtf/mit_kemar.sofa"
SR   = 44100


def _make_sine(dur=2.0, freq=440.0):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)


def test_output_shape():
    hrtf = HRTFDatabase(SOFA)
    mono = _make_sine(1.0)
    proc = BinauralProcessor(hrtf, CirclePath(0.2))
    out  = proc.process(mono, SR)
    assert out.shape == (len(mono), 2), f"Expected ({len(mono)},2) got {out.shape}"


def test_stereo_difference():
    """8D processing must produce different L and R channels."""
    hrtf = HRTFDatabase(SOFA)
    mono = _make_sine(2.0)
    proc = BinauralProcessor(hrtf, CirclePath(0.2))
    out  = proc.process(mono, SR)
    diff = np.abs(out[:, 0] - out[:, 1]).mean()
    assert diff > 1e-4, f"L and R are too similar (diff={diff:.6f}) — rotation not working"


def test_peak_normalised():
    hrtf = HRTFDatabase(SOFA)
    mono = _make_sine(2.0)
    proc = BinauralProcessor(hrtf, CirclePath(0.2))
    out  = proc.process(mono, SR)
    peak = np.abs(out).max()
    assert peak <= 1.0, f"Output clipped: peak={peak}"
    assert peak > 0.1,  f"Output too quiet: peak={peak}"


def test_progress_callback():
    hrtf     = HRTFDatabase(SOFA)
    mono     = _make_sine(1.0)
    progress = []
    proc = BinauralProcessor(hrtf, CirclePath(0.2),
                              on_progress=lambda p: progress.append(p))
    proc.process(mono, SR)
    assert progress[-1] == 1.0, "Progress did not reach 1.0"
    assert len(progress) > 1,   "Progress callback fired too few times"


if __name__ == "__main__":
    for fn in [test_output_shape, test_stereo_difference,
               test_peak_normalised, test_progress_callback]:
        print(f"Running {fn.__name__}...")
        fn()
        print(f"  PASSED")
    print("test_binaural: ALL PASSED")
