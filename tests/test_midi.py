"""
Tests for engine/composition/midi.py

Run: python -m pytest tests/test_midi.py -v
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from engine.composition.midi import (
    MidiData, MidiTrack, Note,
    load_midi, export_midi, render_midi, generate_midi_from_pattern,
)
from engine.composition.sequencer import Pattern


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

def test_note_duration():
    n = Note(pitch=60, start=0.5, end=1.2, velocity=80)
    assert abs(n.duration() - 0.7) < 1e-6


def test_note_serialisation():
    n  = Note(pitch=64, start=1.0, end=2.0, velocity=100, channel=1)
    n2 = Note.from_dict(n.to_dict())
    assert n2.pitch    == 64
    assert n2.start    == 1.0
    assert n2.end      == 2.0
    assert n2.velocity == 100
    assert n2.channel  == 1


def test_midi_data_empty():
    md = MidiData.empty(bpm=140.0)
    assert abs(md.tempo - 140.0) < 1e-6
    assert len(md.tracks) == 1
    assert md.tracks[0].notes == []


def test_midi_data_serialisation():
    md = MidiData.empty()
    md.tracks[0].notes.append(Note(60, 0.0, 1.0, 80))
    d   = md.to_dict()
    md2 = MidiData.from_dict(d)
    assert len(md2.tracks[0].notes) == 1
    assert md2.tracks[0].notes[0].pitch == 60


def test_recalculate_duration():
    md = MidiData.empty()
    md.tracks[0].notes = [
        Note(60, 0.0, 2.5, 80),
        Note(62, 1.0, 4.0, 80),
    ]
    md.recalculate_duration()
    assert md.duration >= 4.0


# ---------------------------------------------------------------------------
# Export + Load round-trip
# ---------------------------------------------------------------------------

def test_export_load_roundtrip(tmp_path):
    md = MidiData.empty(bpm=120.0)
    beat = 0.5   # 120 BPM = 0.5s per beat
    pitches = [60, 62, 64, 67]
    for i, p in enumerate(pitches):
        md.tracks[0].notes.append(
            Note(pitch=p, start=i * beat, end=i * beat + beat * 0.8, velocity=80)
        )
    md.recalculate_duration()

    out = tmp_path / "test.mid"
    export_midi(md, out)
    assert out.exists()

    md2 = load_midi(out)
    assert len(md2.tracks) >= 1
    assert len(md2.tracks[0].notes) == len(pitches)


def test_export_preserves_pitches(tmp_path):
    md = MidiData.empty(bpm=120.0)
    test_pitches = [48, 52, 55, 60, 64, 67, 72]
    beat = 0.5
    for i, p in enumerate(test_pitches):
        md.tracks[0].notes.append(Note(p, i * beat, i * beat + 0.4, 90))
    md.recalculate_duration()

    out = tmp_path / "pitches.mid"
    export_midi(md, out)
    md2 = load_midi(out)

    loaded_pitches = sorted([n.pitch for n in md2.tracks[0].notes])
    assert loaded_pitches == sorted(test_pitches)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_render_shape():
    md = MidiData.empty()
    md.tracks[0].notes.append(Note(60, 0.0, 1.0, 80))
    md.recalculate_duration()

    audio = render_midi(md)
    assert audio.ndim == 2
    assert audio.shape[1] == 2


def test_render_not_silent():
    md = MidiData.empty()
    for i in range(4):
        md.tracks[0].notes.append(Note(60 + i, i * 0.5, i * 0.5 + 0.4, 80))
    md.recalculate_duration()

    audio = render_midi(md)
    assert np.abs(audio).max() > 1e-3


def test_render_normalised():
    md = MidiData.empty()
    for i in range(8):
        md.tracks[0].notes.append(Note(60, i * 0.2, i * 0.2 + 0.15, 127))
    md.recalculate_duration()

    audio = render_midi(md)
    assert np.abs(audio).max() <= 1.0 + 1e-4


def test_render_empty_is_silent():
    md = MidiData.empty()
    audio = render_midi(md)
    assert np.abs(audio).max() < 1e-6


# ---------------------------------------------------------------------------
# Pattern conversion
# ---------------------------------------------------------------------------

def test_generate_from_pattern_track_count():
    pat = Pattern.default()
    md  = generate_midi_from_pattern(pat)
    assert len(md.tracks) == len(pat.tracks)


def test_generate_from_pattern_notes():
    pat = Pattern.default()
    pat.tracks[0].steps[0].velocity  = 100
    pat.tracks[0].steps[8].velocity  = 80
    pat.tracks[1].steps[4].velocity  = 90

    md = generate_midi_from_pattern(pat)
    assert len(md.tracks[0].notes) == 2
    assert len(md.tracks[1].notes) == 1


def test_generate_from_pattern_timing():
    pat = Pattern.default()
    pat.bpm = 120.0
    pat.tracks[0].steps[4].velocity = 100   # step 4, 16th-note duration

    md   = generate_midi_from_pattern(pat)
    note = md.tracks[0].notes[0]
    expected_start = 4 * (60.0 / 120.0 / 4.0)
    assert abs(note.start - expected_start) < 1e-6


def test_generate_preserves_bpm():
    pat = Pattern.default()
    pat.bpm = 160.0
    md  = generate_midi_from_pattern(pat)
    assert abs(md.tempo - 160.0) < 1e-6


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
