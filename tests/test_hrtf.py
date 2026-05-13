"""Tests for engine/spatial/hrtf.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from engine.spatial.hrtf import HRTFDatabase

SOFA = Path(__file__).resolve().parents[1] / "data/hrtf/mit_kemar.sofa"


def test_load():
    db = HRTFDatabase(SOFA)
    assert db.n_measurements > 0, "No measurements loaded"
    assert db.ir_length > 0, "IR length is 0"
    print(f"  Loaded {db.n_measurements} measurements, IR length={db.ir_length}")


def test_hrir_shape():
    db = HRTFDatabase(SOFA)
    l, r = db.get_hrir(0, 0)
    assert l.shape == (db.ir_length,), f"Left IR wrong shape: {l.shape}"
    assert r.shape == (db.ir_length,), f"Right IR wrong shape: {r.shape}"


def test_lateralisation():
    """A lateral source should produce different L and R IRs (ILD present)."""
    db = HRTFDatabase(SOFA)
    l, r = db.get_hrir(90, 0)
    # The two ears must NOT be identical — that proves lateralisation is encoded
    assert not np.allclose(l, r, atol=1e-6), \
        "L and R IRs are identical at az=90 — no lateralisation"


def test_wrap():
    """az=360 and az=0 should give the same HRIR."""
    db = HRTFDatabase(SOFA)
    l0, r0 = db.get_hrir(0, 0)
    l360, r360 = db.get_hrir(360, 0)
    np.testing.assert_array_equal(l0, l360)
    np.testing.assert_array_equal(r0, r360)


if __name__ == "__main__":
    for fn in [test_load, test_hrir_shape, test_lateralisation, test_wrap]:
        print(f"Running {fn.__name__}...")
        fn()
        print(f"  PASSED")
    print("test_hrtf: ALL PASSED")
