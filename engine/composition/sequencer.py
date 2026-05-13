"""
Beat sequencer — Pattern dataclass and real-time Sequencer.

Pattern  : 8 tracks × 16 steps.  Each step stores a velocity (0 = off, 1-127 = on).
Sequencer: background thread that advances steps at the correct 16th-note interval,
           firing on_step(track_idx, step_idx, velocity) for every active step.

Save/load patterns as JSON so sessions persist across restarts.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Step:
    velocity: int = 0          # 0 = silent, 1-127 = on at this velocity


@dataclass
class Track:
    name:       str
    channel:    int            # MIDI channel (0-15); 9 = GM drums
    note:       int            # MIDI note number
    instrument: int            # GM program 0-127 (ignored on drum channel)
    steps:      List[Step] = field(default_factory=lambda: [Step() for _ in range(16)])

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "channel":    self.channel,
            "note":       self.note,
            "instrument": self.instrument,
            "steps":      [s.velocity for s in self.steps],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        steps = [Step(v) for v in d.get("steps", [0] * 16)]
        return cls(
            name=d["name"],
            channel=d["channel"],
            note=d["note"],
            instrument=d.get("instrument", 0),
            steps=steps,
        )


@dataclass
class Pattern:
    name:   str         = "Untitled"
    bpm:    float       = 120.0
    n_steps: int        = 16
    tracks: List[Track] = field(default_factory=list)

    # --- default 8-track kit ---
    @staticmethod
    def default() -> "Pattern":
        return Pattern(
            tracks=[
                Track("Kick",     9, 36, 0),
                Track("Snare",    9, 38, 0),
                Track("Hi-Hat",   9, 42, 0),
                Track("Open Hat", 9, 46, 0),
                Track("Clap",     9, 39, 0),
                Track("Bass",     0, 36, 32),   # Acoustic Bass
                Track("Lead",     1, 60, 80),   # Lead 1 (square)
                Track("Pad",      2, 60, 89),   # Warm Pad
            ]
        )

    def to_dict(self) -> dict:
        return {
            "name":    self.name,
            "bpm":     self.bpm,
            "n_steps": self.n_steps,
            "tracks":  [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pattern":
        return cls(
            name=d.get("name", "Untitled"),
            bpm=float(d.get("bpm", 120.0)),
            n_steps=int(d.get("n_steps", 16)),
            tracks=[Track.from_dict(t) for t in d.get("tracks", [])],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "Pattern":
        return Pattern.from_dict(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Sequencer
# ---------------------------------------------------------------------------

class Sequencer:
    """
    Ticks through a Pattern at BPM tempo.

    Fires on_step(track_idx, step_idx, velocity) on the sequencer thread for
    every active step — the callback must be fast (hand off to audio quickly).
    """

    def __init__(
        self,
        bpm:     float,
        pattern: Pattern,
        on_step: Callable[[int, int, int], None],
    ) -> None:
        self._bpm       = bpm
        self.pattern    = pattern
        self._on_step   = on_step
        self._playing   = False
        self._step      = 0
        self._thread: Optional[threading.Thread] = None
        self._lock      = threading.Lock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_step(self) -> int:
        return self._step

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def bpm(self) -> float:
        return self._bpm

    @bpm.setter
    def bpm(self, value: float) -> None:
        self._bpm = max(20.0, min(300.0, value))

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._playing:
                return
            self._playing = True
            self._step    = 0
            self._thread  = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._playing = False
        self._step    = 0

    # ------------------------------------------------------------------
    # Timing loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while self._playing:
            t0 = time.perf_counter()

            step = self._step
            for track_idx, track in enumerate(self.pattern.tracks):
                velocity = track.steps[step].velocity
                if velocity > 0:
                    try:
                        self._on_step(track_idx, step, velocity)
                    except Exception:
                        pass

            self._step = (step + 1) % self.pattern.n_steps

            # 16th-note interval
            interval = 60.0 / self._bpm / 4.0
            elapsed  = time.perf_counter() - t0
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

        self._step = 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    steps_fired: list[tuple] = []

    def on_step(track_idx, step_idx, velocity):
        steps_fired.append((track_idx, step_idx, velocity))

    pat = Pattern.default()
    # Arm Kick on beats 1, 5, 9, 13 and Snare on 5, 13
    for i in [0, 4, 8, 12]:
        pat.tracks[0].steps[i].velocity = 100
    for i in [4, 12]:
        pat.tracks[1].steps[i].velocity = 90

    seq = Sequencer(bpm=240.0, pattern=pat, on_step=on_step)
    seq.start()
    time.sleep(1.1)   # enough for one full bar at 240 BPM
    seq.stop()

    print(f"Steps fired: {len(steps_fired)}")
    assert len(steps_fired) == 6, f"Expected 6, got {len(steps_fired)}"

    # Round-trip JSON
    tmp = Path("data/samples/test_pattern.json")
    pat.save(tmp)
    pat2 = Pattern.load(tmp)
    assert pat2.tracks[0].steps[0].velocity == 100
    assert pat2.tracks[1].steps[4].velocity == 90
    tmp.unlink()
    print("Pattern save/load OK")

    print("Sequencer self-test passed.")
