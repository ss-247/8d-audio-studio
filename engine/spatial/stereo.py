"""
Stereo widening via mid-side processing — non-rotating spatial mode.
"""

from __future__ import annotations

import numpy as np


class StereoWidener:
    def __init__(self, width: float = 1.5) -> None:
        """width: 0 = mono, 1 = unchanged, 2 = maximum width."""
        self.width = max(0.0, float(width))

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        audio   : float32, shape (N,) mono or (N, 2) stereo
        returns : float32 stereo, shape (N, 2), normalised to −1 dBFS
        """
        if audio.ndim == 1 or (audio.ndim == 2 and audio.shape[1] == 1):
            mono = audio.flatten()
            left = right = mono
        else:
            left  = audio[:, 0]
            right = audio[:, 1]

        mid  = (left + right) * 0.5
        side = (left - right) * 0.5 * self.width

        left_out  = (mid + side).astype(np.float32)
        right_out = (mid - side).astype(np.float32)

        stereo = np.column_stack([left_out, right_out])
        peak = float(np.abs(stereo).max())
        if peak > 1e-6:
            stereo = (stereo * (0.891 / peak)).astype(np.float32)

        return stereo


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    mono = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

    w = StereoWidener(width=1.5)
    stereo = w.process(mono, sr)
    print(f"Input {mono.shape} → output {stereo.shape}")
    print(f"L peak={stereo[:,0].max():.4f}  R peak={stereo[:,1].max():.4f}")
    assert stereo.shape == (sr, 2)
    print("test_stereo: PASSED")
