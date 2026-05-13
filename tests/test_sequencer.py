"""
Tests for engine/composition/sequencer.py and engine/composition/synth.py

Run: python -m pytest tests/test_sequencer.py -v
"""

import time
import threading
from pathlib import Path

import numpy as np
import pytest

from engine.composition.sequencer import Pattern, Step, Track, Sequencer
from engine.composition.synth import FluidSynthEngine, _make_kick, _make_snare, _make_hihat


# ---------------------------------------------------------------------------
# Pattern data model
# ---------------------------------------------------------------------------

def test_default_pattern_has_eight_tracks():
    pat = Pattern.default()
    assert len(pat.tracks) == 8


def test_default_pattern_has_16_steps_per_track():
    pat = Pattern.default()
    for track in pat.tracks:
        assert len(track.steps) == 16


def test_step_toggle():
    step = Step(velocity=0)
    step.velocity = 100
    assert step.velocity == 100
    step.velocity = 0
    assert step.velocity == 0


def test_pattern_serialisation_round_trip():
    pat = Pattern.default()
    pat.tracks[0].steps[0].velocity = 100
    pat.tracks[1].steps[4].velocity = 80
    pat.bpm = 140.0

    d    = pat.to_dict()
    pat2 = Pattern.from_dict(d)

    assert abs(pat2.bpm - 140.0) < 1e-6
    assert pat2.tracks[0].steps[0].velocity == 100
    assert pat2.tracks[1].steps[4].velocity == 80
    assert pat2.tracks[0].steps[1].velocity == 0


def test_pattern_save_load(tmp_path):
    pat = Pattern.default()
    pat.tracks[2].steps[8].velocity = 127
    pat.name = "test_pattern"

    save_path = tmp_path / "pattern.json"
    pat.save(save_path)
    loaded = Pattern.load(save_path)

    assert loaded.name == "test_pattern"
    assert loaded.tracks[2].steps[8].velocity == 127
    assert loaded.tracks[2].steps[7].velocity == 0


def test_track_serialisation():
    track = Track("Kick", 9, 36, 0)
    track.steps[3].velocity = 75
    d = track.to_dict()
    t2 = Track.from_dict(d)
    assert t2.name == "Kick"
    assert t2.note == 36
    assert t2.steps[3].velocity == 75


# ---------------------------------------------------------------------------
# Sequencer timing
# ---------------------------------------------------------------------------

def test_sequencer_fires_correct_steps():
    """Arm 4 steps; run at high BPM; check exactly 4 callbacks fire."""
    fired = []

    def on_step(t, s, v):
        fired.append((t, s, v))

    pat = Pattern.default()
    for i in [0, 4, 8, 12]:
        pat.tracks[0].steps[i].velocity = 100

    seq = Sequencer(bpm=960.0, pattern=pat, on_step=on_step)
    seq.start()
    time.sleep(0.35)
    seq.stop()

    assert len(fired) >= 4, f"Expected >= 4 steps, got {len(fired)}"
    assert all(s in [0, 4, 8, 12] for _, s, _ in fired)


def test_sequencer_stops_cleanly():
    pat = Pattern.default()
    pat.tracks[0].steps[0].velocity = 100
    seq = Sequencer(bpm=240.0, pattern=pat, on_step=lambda t, s, v: None)
    seq.start()
    assert seq.is_playing
    seq.stop()
    time.sleep(0.05)
    assert not seq.is_playing
    assert seq.current_step == 0


def test_sequencer_bpm_setter():
    pat = Pattern.default()
    seq = Sequencer(bpm=120.0, pattern=pat, on_step=lambda t, s, v: None)
    seq.bpm = 200.0
    assert abs(seq.bpm - 200.0) < 1e-6


def test_sequencer_all_steps_visited():
    steps_seen = []
    done = threading.Event()

    def on_step(t, s, v):
        steps_seen.append(s)
        if len(set(steps_seen)) >= 16:
            done.set()

    pat = Pattern.default()
    for i in range(16):
        pat.tracks[0].steps[i].velocity = 100

    seq = Sequencer(bpm=960.0, pattern=pat, on_step=on_step)
    seq.start()
    done.wait(timeout=2.0)
    seq.stop()

    assert len(set(steps_seen)) >= 16, f"Not all steps visited: {set(steps_seen)}"


# ---------------------------------------------------------------------------
# NumPy synth samples
# ---------------------------------------------------------------------------

def test_kick_shape_and_energy():
    s = _make_kick(100)
    assert s.ndim == 1
    assert len(s) > 1000
    assert np.abs(s).max() > 0.1


def test_snare_shape_and_energy():
    s = _make_snare(100)
    assert s.ndim == 1
    assert np.abs(s).max() > 0.05


def test_hihat_open_longer_than_closed():
    closed = _make_hihat(100, open_hat=False)
    opened = _make_hihat(100, open_hat=True)
    assert len(opened) > len(closed)


def test_velocity_scales_amplitude():
    low  = _make_kick(32)
    high = _make_kick(127)
    assert np.abs(high).max() > np.abs(low).max() * 1.5


# ---------------------------------------------------------------------------
# FluidSynthEngine render
# ---------------------------------------------------------------------------

def test_render_pattern_shape():
    engine = FluidSynthEngine()
    pat = Pattern.default()
    pat.tracks[0].steps[0].velocity = 100

    audio = engine.render_pattern(pat, bpm=120.0)
    assert audio.ndim == 2
    assert audio.shape[1] == 2


def test_render_pattern_not_silent():
    engine = FluidSynthEngine()
    pat = Pattern.default()
    for i in range(4):
        pat.tracks[0].steps[i * 4].velocity = 100

    audio = engine.render_pattern(pat, bpm=120.0)
    assert np.abs(audio).max() > 1e-3


def test_render_pattern_normalised():
    engine = FluidSynthEngine()
    pat = Pattern.default()
    for track in pat.tracks:
        for step in track.steps:
            step.velocity = 127

    audio = engine.render_pattern(pat, bpm=120.0)
    assert np.abs(audio).max() <= 1.0 + 1e-4


def test_backend_property():
    engine = FluidSynthEngine()
    assert engine.backend in ("fluidsynth", "numpy-fallback")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
