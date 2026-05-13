"""
HRTF database — loads the MIT KEMAR SOFA file and provides fast HRIR lookup.

All HRIRs are preloaded into NumPy arrays at init.
get_hrir() uses brute-force nearest-neighbour search (710 measurements,
azimuth wrap-around handled) which is plenty fast for per-frame lookup.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np


class HRTFDatabase:
    def __init__(self, sofa_path: Path) -> None:
        sofa_path = Path(sofa_path)
        if not sofa_path.exists():
            raise FileNotFoundError(
                f"HRTF file not found: {sofa_path}\n"
                "Run:  python scripts/setup_assets.py"
            )

        import sofar
        sofa = sofar.read_sofa(str(sofa_path))

        # SourcePosition: (M, 3)  [azimuth_deg, elevation_deg, distance_m]
        positions = np.asarray(sofa.SourcePosition, dtype=np.float32)
        self._azimuths   = positions[:, 0]   # 0–360 °
        self._elevations = positions[:, 1]   # −40–+90 °

        # Data_IR: (M, 2, L)   axis-1: 0 = left ear, 1 = right ear
        ir = np.asarray(sofa.Data_IR, dtype=np.float32)
        self._ir_left  = ir[:, 0, :]   # (M, L)
        self._ir_right = ir[:, 1, :]   # (M, L)
        self._ir_length = ir.shape[2]

    def get_hrir(
        self, azimuth_deg: float, elevation_deg: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return (left_ir, right_ir) for the nearest measured position."""
        az = float(azimuth_deg) % 360.0
        el = float(np.clip(elevation_deg, -40.0, 90.0))

        diff_az = np.abs(self._azimuths - az)
        diff_az = np.minimum(diff_az, 360.0 - diff_az)   # wrap
        diff_el = np.abs(self._elevations - el)

        idx = int(np.argmin(diff_az ** 2 + diff_el ** 2))
        return self._ir_left[idx], self._ir_right[idx]

    @property
    def ir_length(self) -> int:
        return self._ir_length

    @property
    def n_measurements(self) -> int:
        return len(self._azimuths)


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    path = Path(__file__).resolve().parents[2] / "data/hrtf/mit_kemar.sofa"
    print(f"Loading HRTF from {path} ...")
    db = HRTFDatabase(path)
    print(f"  {db.n_measurements} measurements, IR length = {db.ir_length} samples")

    for az, el in [(0, 0), (90, 0), (180, 0), (270, 0), (45, 30)]:
        l, r = db.get_hrir(az, el)
        print(f"  az={az:3d} el={el:3d} → left peak={l.max():.4f}  right peak={r.max():.4f}")

    print("test_hrtf: PASSED")
