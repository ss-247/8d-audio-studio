"""
Tests for engine/effects/chain.py

Run: python -m pytest tests/test_effects.py -v
  or: python tests/test_effects.py
"""

import numpy as np
import pytest

from engine.effects.chain import EffectsChain

SR    = 44100
DUR   = 1.0   # seconds
BLOCK = 2048

_t    = np.linspace(0, DUR, int(SR * DUR), endpoint=False, dtype=np.float32)
MONO  = np.sin(2 * np.pi * 440 * _t) * 0.5          # (N,)
STEREO = np.stack([MONO, MONO * 0.8], axis=1)        # (N, 2)


# ---------------------------------------------------------------------------
# Basic shape contract
# ---------------------------------------------------------------------------

def test_process_stereo_shape():
    chain = EffectsChain()
    out = chain.process(STEREO.copy(), SR)
    assert out.shape == STEREO.shape, f"Expected {STEREO.shape}, got {out.shape}"


def test_process_mono_shape():
    chain = EffectsChain()
    out = chain.process(MONO.copy(), SR)
    assert out.shape == MONO.shape, f"Expected {MONO.shape}, got {out.shape}"


# ---------------------------------------------------------------------------
# Reverb effect is audible
# ---------------------------------------------------------------------------

def test_reverb_changes_output():
    """With reverb on, output must differ from the dry signal."""
    chain = EffectsChain()
    chain.reverb_enabled = True
    chain.reverb_room_size = 0.9
    chain.reverb_wet_level = 0.5
    chain.reverb_dry_level = 0.5

    out = chain.process(STEREO.copy(), SR)
    diff = np.abs(out - STEREO).mean()
    assert diff > 1e-4, f"Reverb produced no audible change (mean diff={diff})"


def test_reverb_off_is_closer_to_dry():
    """Reverb-off output should be closer to dry than reverb-on output."""
    on_chain = EffectsChain()
    on_chain.reverb_room_size = 0.9
    on_chain.reverb_wet_level = 0.8
    on_chain.reverb_dry_level = 0.2
    on_chain.reverb_enabled = True

    off_chain = EffectsChain()
    off_chain.reverb_enabled = False

    out_on  = on_chain.process(STEREO.copy(), SR)
    out_off = off_chain.process(STEREO.copy(), SR)

    diff_on  = np.abs(out_on  - STEREO).mean()
    diff_off = np.abs(out_off - STEREO).mean()
    assert diff_on > diff_off, "Reverb-on output should differ more from dry"


# ---------------------------------------------------------------------------
# Limiter keeps peak below threshold
# ---------------------------------------------------------------------------

def test_limiter_reduces_peak():
    """Limiter must reduce the peak of an over-loud signal."""
    loud = STEREO * 5.0  # push well above 0 dBFS
    chain_on = EffectsChain()
    chain_on.hp_enabled     = False
    chain_on.lp_enabled     = False
    chain_on.reverb_enabled = False
    chain_on.chorus_enabled = False
    chain_on.comp_enabled   = False
    chain_on.limiter_enabled = True
    chain_on.limiter_threshold_db = -3.0

    chain_off = EffectsChain()
    chain_off.hp_enabled      = False
    chain_off.lp_enabled      = False
    chain_off.reverb_enabled  = False
    chain_off.chorus_enabled  = False
    chain_off.comp_enabled    = False
    chain_off.limiter_enabled = False

    out_on  = chain_on.process(loud.copy(), SR)
    out_off = chain_off.process(loud.copy(), SR)

    peak_on  = np.abs(out_on).max()
    peak_off = np.abs(out_off).max()
    assert peak_on < peak_off, f"Limiter-on peak ({peak_on:.4f}) should be less than limiter-off peak ({peak_off:.4f})"


# ---------------------------------------------------------------------------
# Streaming: process_block preserves shape and doesn't crash
# ---------------------------------------------------------------------------

def test_process_block_streaming():
    chain = EffectsChain()
    chain.reset_stream()
    collected = []
    for i in range(0, len(STEREO), BLOCK):
        chunk = STEREO[i : i + BLOCK]
        out   = chain.process_block(chunk, SR)
        assert out.shape == chunk.shape, f"Block shape mismatch at i={i}"
        collected.append(out)
    full = np.concatenate(collected, axis=0)
    assert full.shape == STEREO.shape


# ---------------------------------------------------------------------------
# Dirty flag triggers rebuild
# ---------------------------------------------------------------------------

def test_mark_dirty_changes_output():
    chain = EffectsChain()
    out1 = chain.process(STEREO.copy(), SR)

    chain.reverb_room_size = 0.99
    chain.mark_dirty()
    out2 = chain.process(STEREO.copy(), SR)

    # Outputs should differ after parameter change
    assert not np.allclose(out1, out2), "mark_dirty did not cause different output"


# ---------------------------------------------------------------------------
# Preset round-trip
# ---------------------------------------------------------------------------

def test_preset_save_load_delete():
    chain = EffectsChain()
    chain.reverb_room_size  = 0.77
    chain.comp_threshold_db = -25.0

    name = "__pytest_preset__"
    chain.save_preset(name)

    assert name in EffectsChain.list_presets(), "Preset not found after save"

    loaded = EffectsChain.load_preset(name)
    assert loaded is not None
    assert abs(loaded.reverb_room_size  - 0.77)  < 1e-6
    assert abs(loaded.comp_threshold_db - (-25.0)) < 1e-6

    EffectsChain.delete_preset(name)
    assert name not in EffectsChain.list_presets(), "Preset still present after delete"


def test_load_nonexistent_preset_returns_none():
    result = EffectsChain.load_preset("__nonexistent_xyz__")
    assert result is None


# ---------------------------------------------------------------------------
# to_dict / from_dict
# ---------------------------------------------------------------------------

def test_serialisation_round_trip():
    chain = EffectsChain()
    chain.chorus_rate_hz = 2.5
    chain.hp_enabled     = False

    d      = chain.to_dict()
    loaded = EffectsChain.from_dict(d)

    assert abs(loaded.chorus_rate_hz - 2.5) < 1e-6
    assert loaded.hp_enabled is False


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
