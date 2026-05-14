"""
MIDI engine — load, edit, render, and export MIDI data.

Rendering uses FluidSynth via pretty_midi when available; falls back to a
NumPy sine-wave renderer so the piano roll works without any extra setup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

_SR = 44100


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Note:
    pitch:    int           # MIDI pitch 21 (A0) – 108 (C8)
    start:    float         # start time in seconds
    end:      float         # end time in seconds
    velocity: int           # 1–127
    channel:  int = 0

    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict:
        return {
            "pitch": self.pitch, "start": self.start,
            "end": self.end, "velocity": self.velocity,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Note":
        return cls(**d)


@dataclass
class MidiTrack:
    name:       str
    instrument: int                      # GM program 0–127
    channel:    int
    notes:      List[Note] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "instrument": self.instrument,
            "channel": self.channel,
            "notes": [n.to_dict() for n in self.notes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MidiTrack":
        notes = [Note.from_dict(n) for n in d.get("notes", [])]
        return cls(
            name=d["name"],
            instrument=d.get("instrument", 0),
            channel=d.get("channel", 0),
            notes=notes,
        )

    @staticmethod
    def empty(name: str = "Track 1", instrument: int = 0, channel: int = 0) -> "MidiTrack":
        return MidiTrack(name=name, instrument=instrument, channel=channel)


@dataclass
class MidiData:
    tempo:    float                      # BPM
    duration: float                      # total length in seconds
    tracks:   List[MidiTrack] = field(default_factory=list)

    @staticmethod
    def empty(bpm: float = 120.0) -> "MidiData":
        return MidiData(
            tempo=bpm,
            duration=16.0,
            tracks=[MidiTrack.empty()],
        )

    def to_dict(self) -> dict:
        return {
            "tempo": self.tempo,
            "duration": self.duration,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MidiData":
        return cls(
            tempo=float(d.get("tempo", 120.0)),
            duration=float(d.get("duration", 16.0)),
            tracks=[MidiTrack.from_dict(t) for t in d.get("tracks", [])],
        )

    def recalculate_duration(self) -> None:
        """Update duration to cover all notes."""
        ends = [n.end for t in self.tracks for n in t.notes]
        self.duration = max(ends) + 1.0 if ends else 16.0


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_midi(path: Path) -> MidiData:
    """Load a .mid file using pretty_midi."""
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(str(path))

    try:
        tempo = float(pm.estimate_tempo())
    except Exception:
        tempo = 120.0

    tracks = []
    for inst in pm.instruments:
        notes = [
            Note(
                pitch=n.pitch,
                start=n.start,
                end=n.end,
                velocity=n.velocity,
                channel=inst.program,
            )
            for n in inst.notes
        ]
        tracks.append(MidiTrack(
            name=inst.name or f"Track {len(tracks)+1}",
            instrument=inst.program,
            channel=len(tracks) % 16,
            notes=notes,
        ))

    if not tracks:
        tracks = [MidiTrack.empty()]

    duration = pm.get_end_time()
    return MidiData(tempo=tempo, duration=max(duration, 1.0), tracks=tracks)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_midi(midi_data: MidiData, path: Path) -> None:
    """Write MidiData to a .mid file using pretty_midi."""
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=midi_data.tempo)

    for track in midi_data.tracks:
        inst = pretty_midi.Instrument(
            program=track.instrument,
            is_drum=(track.channel == 9),
            name=track.name,
        )
        for note in sorted(track.notes, key=lambda n: n.start):
            if note.end > note.start:
                inst.notes.append(pretty_midi.Note(
                    velocity=max(1, min(127, note.velocity)),
                    pitch=max(0, min(127, note.pitch)),
                    start=max(0.0, note.start),
                    end=note.end,
                ))
        pm.instruments.append(inst)

    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_midi(midi_data: MidiData, sf2_path: Optional[Path] = None) -> np.ndarray:
    """
    Render MidiData to a stereo float32 numpy array.

    Tries FluidSynth (via pretty_midi) when sf2_path is provided and
    FluidSynth is installed; falls back to NumPy sine-wave synthesis.
    """
    if sf2_path is not None and sf2_path.exists():
        try:
            return _render_fluidsynth(midi_data, sf2_path)
        except Exception:
            pass

    return _render_numpy(midi_data)


def _render_fluidsynth(midi_data: MidiData, sf2_path: Path) -> np.ndarray:
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=midi_data.tempo)
    for track in midi_data.tracks:
        inst = pretty_midi.Instrument(program=track.instrument, name=track.name)
        for note in track.notes:
            if note.end > note.start:
                inst.notes.append(pretty_midi.Note(
                    velocity=note.velocity, pitch=note.pitch,
                    start=note.start, end=note.end,
                ))
        pm.instruments.append(inst)

    audio = pm.fluidsynth(fs=_SR, sf2_path=str(sf2_path))
    stereo = np.stack([audio, audio], axis=1).astype(np.float32)
    _normalise(stereo)
    return stereo


def _render_numpy(midi_data: MidiData) -> np.ndarray:
    """Pure NumPy sine-wave MIDI renderer."""
    from engine.composition.synth import _make_tone, _synth_sample

    total_n = int(_SR * (midi_data.duration + 1.5))
    out = np.zeros((total_n, 2), dtype=np.float32)

    for track in midi_data.tracks:
        for note in track.notes:
            dur = note.duration()
            if dur <= 0:
                continue
            if track.channel == 9:
                sample = _synth_sample(9, note.pitch, note.velocity)
            else:
                sample = _make_tone(note.pitch, note.velocity, min(dur, 8.0))
            s_n = int(note.start * _SR)
            e_n = min(s_n + len(sample), total_n)
            n   = e_n - s_n
            out[s_n:e_n, 0] += sample[:n]
            out[s_n:e_n, 1] += sample[:n]

    _normalise(out)
    return out


def _normalise(audio: np.ndarray) -> None:
    peak = np.abs(audio).max()
    if peak > 1e-6:
        audio *= 0.9 / peak


# ---------------------------------------------------------------------------
# Pattern → MIDI conversion
# ---------------------------------------------------------------------------

def generate_midi_from_pattern(pattern) -> MidiData:
    """Convert a sequencer Pattern to MidiData."""
    step_dur = 60.0 / pattern.bpm / 4.0
    tracks = []
    for track in pattern.tracks:
        notes = []
        for step_idx, step in enumerate(track.steps):
            if step.velocity > 0:
                t = step_idx * step_dur
                notes.append(Note(
                    pitch=track.note,
                    start=t,
                    end=t + step_dur * 0.85,
                    velocity=step.velocity,
                    channel=track.channel,
                ))
        tracks.append(MidiTrack(
            name=track.name,
            instrument=track.instrument,
            channel=track.channel,
            notes=notes,
        ))
    duration = pattern.n_steps * step_dur
    return MidiData(tempo=pattern.bpm, duration=duration, tracks=tracks)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("MIDI engine self-test ...")

    # Build a simple melody
    md = MidiData.empty(bpm=120.0)
    md.tracks[0].name = "Piano"
    beat = 60.0 / 120.0
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    for i, p in enumerate(pitches):
        md.tracks[0].notes.append(
            Note(pitch=p, start=i * beat, end=i * beat + beat * 0.8, velocity=80)
        )
    md.recalculate_duration()

    # Render
    audio = render_midi(md)
    assert audio.ndim == 2 and audio.shape[1] == 2
    assert np.abs(audio).max() > 1e-3
    print(f"  Render: {audio.shape}  peak={np.abs(audio).max():.4f}")

    # Export + load round-trip
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        tmp = Path(f.name)
    export_midi(md, tmp)
    md2 = load_midi(tmp)
    tmp.unlink()
    assert len(md2.tracks) > 0
    assert len(md2.tracks[0].notes) == len(pitches)
    print(f"  Export/load round-trip: {len(md2.tracks[0].notes)} notes OK")

    # Pattern conversion
    from engine.composition.sequencer import Pattern
    pat = Pattern.default()
    pat.tracks[0].steps[0].velocity = 100
    pat.tracks[0].steps[4].velocity = 100
    midi = generate_midi_from_pattern(pat)
    assert len(midi.tracks) == 8
    assert len(midi.tracks[0].notes) == 2
    print("  generate_midi_from_pattern: OK")

    print("Self-test passed.")
