"""
Frame-by-frame HRTF convolution pipeline (overlap-add).

Input audio is divided into non-overlapping blocks of size `hop`.
Each block is convolved with the HRIR for its centre-time angle.
Outputs are overlap-added so convolution tails accumulate correctly.
This gives accurate spatialisation even as the HRIR changes every frame.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np
from scipy.signal import fftconvolve

from engine.spatial.hrtf import HRTFDatabase
from engine.spatial.rotation import RotationPath


class BinauralProcessor:
    def __init__(
        self,
        hrtf_db: HRTFDatabase,
        rotation_path: RotationPath,
        on_progress: Optional[Callable[[float], None]] = None,
        on_angle: Optional[Callable[[float, float], None]] = None,
    ) -> None:
        self._hrtf = hrtf_db
        self._path = rotation_path
        self._on_progress = on_progress
        self._on_angle = on_angle

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Convolve audio with a rotating HRTF.

        audio       : float32, shape (N,) or (N, channels) — mixed to mono internally
        sample_rate : must match the source audio
        returns     : float32 stereo, shape (N, 2), normalised to −1 dBFS
        """
        # Mix to mono
        if audio.ndim > 1:
            mono = audio.mean(axis=1).astype(np.float32)
        else:
            mono = audio.astype(np.float32)

        n = len(mono)
        ir_len = self._hrtf.ir_length
        hop = ir_len  # non-overlapping input blocks

        n_hops = (n + hop - 1) // hop
        # Each padded frame is exactly `hop` samples, so the last overlap-add
        # extends to n_hops*hop + ir_len - 1 (may exceed n + ir_len - 1).
        out_len = n_hops * hop + ir_len - 1
        left_buf  = np.zeros(out_len, dtype=np.float64)
        right_buf = np.zeros(out_len, dtype=np.float64)

        for i in range(n_hops):
            start = i * hop
            end   = min(start + hop, n)

            frame = mono[start:end]
            if len(frame) < hop:
                frame = np.pad(frame, (0, hop - len(frame)))

            # Centre-time of this block
            t = (start + hop * 0.5) / sample_rate
            az, el = self._path.get_angle(t)

            if self._on_angle is not None:
                self._on_angle(az, el)

            hrir_l, hrir_r = self._hrtf.get_hrir(az, el)

            # fftconvolve: output length = hop + ir_len − 1
            lc = fftconvolve(frame, hrir_l)
            rc = fftconvolve(frame, hrir_r)

            left_buf[start : start + len(lc)]  += lc
            right_buf[start : start + len(rc)] += rc

            if self._on_progress is not None and i % 20 == 0:
                self._on_progress(i / n_hops)

        left_out  = left_buf[:n].astype(np.float32)
        right_out = right_buf[:n].astype(np.float32)

        stereo = np.column_stack([left_out, right_out])

        # Normalise to −1 dBFS
        peak = float(np.abs(stereo).max())
        if peak > 1e-6:
            stereo = (stereo * (0.891 / peak)).astype(np.float32)

        if self._on_progress is not None:
            self._on_progress(1.0)

        return stereo


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys, time
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from engine.spatial.hrtf import HRTFDatabase
    from engine.spatial.rotation import CirclePath
    import soundfile as sf

    sofa = Path(__file__).resolve().parents[2] / "data/hrtf/mit_kemar.sofa"
    print("Loading HRTF...")
    hrtf = HRTFDatabase(sofa)

    sr = 44100
    dur = 4.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    mono = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)

    path = CirclePath(speed_hz=0.25)
    proc = BinauralProcessor(
        hrtf, path,
        on_progress=lambda p: print(f"\r  {p*100:.0f}%", end="", flush=True),
    )

    t0 = time.time()
    stereo = proc.process(mono, sr)
    elapsed = time.time() - t0
    print(f"\n  Processed {dur:.0f}s in {elapsed:.2f}s — shape {stereo.shape} peak {np.abs(stereo).max():.4f}")

    out = Path(__file__).resolve().parents[2] / "data/samples/test_binaural.wav"
    sf.write(str(out), stereo, sr, subtype="PCM_24")
    print(f"  Written: {out}")
    print("test_binaural: PASSED")
