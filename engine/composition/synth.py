"""
FluidSynthEngine — wraps pyfluidsynth for GM sound playback.

Falls back to a pure-NumPy drum synthesizer when FluidSynth DLLs are not
installed, so the sequencer works out-of-the-box without any extra setup.

Usage
-----
synth = FluidSynthEngine()
synth.load_soundfont("data/soundfonts/GeneralUser.sf2")  # optional
synth.note_on(9, 36, 100)   # channel 9 (drums), note 36 (kick), vel 100
synth.note_off(9, 36)

# Offline render
audio = synth.render_pattern(pattern, bpm=120.0)
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

from engine.composition.sequencer import Pattern, Track

_SR = 44100


# ---------------------------------------------------------------------------
# Pure-NumPy drum / tone synthesizer (used when FluidSynth is unavailable)
# ---------------------------------------------------------------------------

def _make_kick(velocity: int = 100) -> np.ndarray:
    dur = 0.35
    n   = int(_SR * dur)
    t   = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    # Frequency sweep: 180 Hz → 40 Hz
    freq  = np.exp(np.linspace(np.log(180), np.log(40), n))
    phase = 2 * np.pi * np.cumsum(freq) / _SR
    amp   = np.exp(-t * 18)
    return np.sin(phase).astype(np.float32) * amp * (velocity / 127.0) * 0.85


def _make_snare(velocity: int = 100) -> np.ndarray:
    dur = 0.15
    n   = int(_SR * dur)
    t   = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    noise = np.random.default_rng(42).standard_normal(n).astype(np.float32)
    tone  = np.sin(2 * np.pi * 185 * t)
    amp   = np.exp(-t * 28)
    return (noise * 0.65 + tone * 0.35) * amp * (velocity / 127.0) * 0.70


def _make_hihat(velocity: int = 100, open_hat: bool = False) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    dur   = 0.25 if open_hat else 0.045
    n     = int(_SR * dur)
    t     = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    noise = np.random.default_rng(7).standard_normal(n).astype(np.float32)
    sos   = butter(4, 7000 / (_SR / 2), btype="high", output="sos")
    filt  = sosfilt(sos, noise).astype(np.float32)
    decay = 8 if open_hat else 80
    amp   = np.exp(-t * decay)
    return filt * amp * (velocity / 127.0) * 0.55


def _make_clap(velocity: int = 100) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    # Three overlapping noise bursts
    dur  = 0.12
    n    = int(_SR * dur)
    t    = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    rng  = np.random.default_rng(13)
    out  = np.zeros(n, dtype=np.float32)
    for delay in [0, 0.008, 0.016]:
        d = int(delay * _SR)
        burst = rng.standard_normal(n - d).astype(np.float32)
        amp   = np.exp(-np.linspace(0, dur - delay, n - d) * 35)
        out[d:] += burst * amp
    sos = butter(3, 4000 / (_SR / 2), btype="high", output="sos")
    return sosfilt(sos, out).astype(np.float32) * (velocity / 127.0) * 0.75


def _make_tone(note: int, velocity: int = 100, dur: float = 0.25) -> np.ndarray:
    """Sine with simple ADSR envelope for melodic tracks."""
    freq  = 440.0 * (2 ** ((note - 69) / 12.0))
    n     = int(_SR * dur)
    t     = np.linspace(0, dur, n, endpoint=False, dtype=np.float32)
    wave  = np.sin(2 * np.pi * freq * t)
    a_n   = min(int(0.005 * _SR), n // 4)
    r_n   = min(int(0.04  * _SR), n // 4)
    env   = np.ones(n, dtype=np.float32)
    if a_n:
        env[:a_n]  = np.linspace(0, 1, a_n)
    if r_n:
        env[-r_n:] = np.linspace(1, 0, r_n)
    return wave * env * (velocity / 127.0) * 0.55


# MIDI note → generator for GM drum channel
_DRUM_MAP = {
    35: lambda v: _make_kick(v),
    36: lambda v: _make_kick(v),
    38: lambda v: _make_snare(v),
    40: lambda v: _make_snare(v),
    42: lambda v: _make_hihat(v, open_hat=False),
    44: lambda v: _make_hihat(v, open_hat=False),
    46: lambda v: _make_hihat(v, open_hat=True),
    39: lambda v: _make_clap(v),
    49: lambda v: _make_hihat(v, open_hat=True),   # crash approx.
}


def _synth_sample(channel: int, note: int, velocity: int) -> np.ndarray:
    """Generate a short audio sample for one note using the NumPy synth."""
    if channel == 9:
        gen = _DRUM_MAP.get(note)
        return gen(velocity) if gen else _make_hihat(velocity)
    return _make_tone(note, velocity)


# ---------------------------------------------------------------------------
# FluidSynthEngine
# ---------------------------------------------------------------------------

class FluidSynthEngine:
    """
    Plays notes via FluidSynth when available, falls back to NumPy synth.

    The sounddevice OutputStream is kept open for the lifetime of the engine.
    Pending audio samples are mixed into a ring buffer consumed by the callback.
    """

    _BUFSIZE = 4096   # ring buffer frames

    def __init__(self) -> None:
        self._sf_loaded   = False
        self._fs          = None          # fluidsynth.Synth | None
        self._use_fluid   = False
        self._lock        = threading.Lock()
        self._mix_buf     = np.zeros(self._BUFSIZE * 2, dtype=np.float32)
        self._write_pos   = 0
        self._read_pos    = 0
        self._stream: Optional[sd.OutputStream] = None
        self._stream_lock = threading.Lock()

        self._try_init_fluidsynth()

    # ------------------------------------------------------------------
    # FluidSynth init (optional)
    # ------------------------------------------------------------------

    def _try_init_fluidsynth(self) -> None:
        try:
            import fluidsynth
            fs = fluidsynth.Synth(samplerate=float(_SR))
            fs.start(driver="dsound")
            self._fs       = fs
            self._use_fluid = True
        except Exception:
            self._use_fluid = False
            self._open_fallback_stream()

    def load_soundfont(self, path: Path) -> bool:
        """Load an SF2 file. Returns True on success."""
        if not self._use_fluid or self._fs is None:
            return False
        try:
            sfid = self._fs.sfload(str(path))
            if sfid == -1:
                return False
            for ch in range(16):
                self._fs.program_select(ch, sfid, 0, 0)
            self._sf_loaded = True
            return True
        except Exception:
            return False

    def set_instrument(self, channel: int, program: int) -> None:
        if self._use_fluid and self._fs is not None:
            try:
                self._fs.program_change(channel, program)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Playback API
    # ------------------------------------------------------------------

    def note_on(self, channel: int, note: int, velocity: int) -> None:
        if self._use_fluid and self._fs is not None:
            try:
                self._fs.noteon(channel, note, velocity)
                return
            except Exception:
                pass
        # Fallback: generate sample and queue into mix buffer
        sample = _synth_sample(channel, note, velocity)
        self._queue_sample(sample)

    def note_off(self, channel: int, note: int) -> None:
        if self._use_fluid and self._fs is not None:
            try:
                self._fs.noteoff(channel, note)
            except Exception:
                pass
        # Fallback: envelope handles note-off naturally

    # ------------------------------------------------------------------
    # Offline render
    # ------------------------------------------------------------------

    def render_pattern(self, pattern: Pattern, bpm: float) -> np.ndarray:
        """
        Render one full loop of a pattern to a stereo float32 array offline.
        Uses NumPy synth regardless of FluidSynth availability for determinism.
        """
        step_dur   = 60.0 / bpm / 4.0          # 16th note in seconds
        pattern_dur = step_dur * pattern.n_steps
        total_n    = int(_SR * (pattern_dur + 1.0))  # +1 s for tails
        out        = np.zeros((total_n, 2), dtype=np.float32)

        for step_idx in range(pattern.n_steps):
            t_start = int(step_idx * step_dur * _SR)
            for track in pattern.tracks:
                vel = track.steps[step_idx].velocity
                if vel == 0:
                    continue
                sample = _synth_sample(track.channel, track.note, vel)
                end    = min(t_start + len(sample), total_n)
                n      = end - t_start
                out[t_start:end, 0] += sample[:n]
                out[t_start:end, 1] += sample[:n]

        # Normalise
        peak = np.abs(out).max()
        if peak > 1e-6:
            out *= 0.9 / peak
        return out

    # ------------------------------------------------------------------
    # Fallback stream (NumPy synth)
    # ------------------------------------------------------------------

    def _open_fallback_stream(self) -> None:
        try:
            stream = sd.OutputStream(
                samplerate=_SR,
                channels=2,
                dtype="float32",
                blocksize=512,
                callback=self._fallback_callback,
            )
            with self._stream_lock:
                self._stream = stream
            stream.start()
        except Exception:
            pass

    def _fallback_callback(self, outdata: np.ndarray, frames: int, time, status) -> None:
        with self._lock:
            avail = (self._write_pos - self._read_pos) % len(self._mix_buf)
            n     = min(frames, avail // 2)
            for i in range(n):
                idx = (self._read_pos + i * 2) % len(self._mix_buf)
                outdata[i, 0] = self._mix_buf[idx]
                outdata[i, 1] = self._mix_buf[idx + 1]
            self._read_pos = (self._read_pos + n * 2) % len(self._mix_buf)
        if n < frames:
            outdata[n:] = 0

    def _queue_sample(self, sample: np.ndarray) -> None:
        with self._lock:
            for s in sample:
                idx = self._write_pos % len(self._mix_buf)
                self._mix_buf[idx]     = s   # L
                self._mix_buf[idx + 1] = s   # R
                self._write_pos = (self._write_pos + 2) % len(self._mix_buf)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._stream_lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop(); stream.close()
            except Exception:
                pass
        if self._fs is not None:
            try:
                self._fs.delete()
            except Exception:
                pass

    @property
    def backend(self) -> str:
        return "fluidsynth" if self._use_fluid else "numpy-fallback"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time as _time
    from engine.composition.sequencer import Pattern

    print("FluidSynthEngine self-test ...")
    engine = FluidSynthEngine()
    print(f"  Backend: {engine.backend}")

    # Render a simple pattern
    pat = Pattern.default()
    pat.tracks[0].steps[0].velocity  = 100   # Kick  on 1
    pat.tracks[1].steps[4].velocity  = 90    # Snare on 5
    pat.tracks[2].steps[2].velocity  = 80    # HH    on 3

    audio = engine.render_pattern(pat, bpm=120.0)
    assert audio.ndim == 2 and audio.shape[1] == 2, f"Bad shape: {audio.shape}"
    assert np.abs(audio).max() > 1e-3, "Silent render"
    print(f"  render_pattern: {audio.shape}  peak={np.abs(audio).max():.4f}")

    # Live note test (plays for 0.5 s)
    engine.note_on(9, 36, 100)   # kick
    _time.sleep(0.1)
    engine.note_on(9, 38, 90)    # snare
    _time.sleep(0.4)
    engine.close()
    print("Self-test passed.")
