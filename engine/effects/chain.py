"""
Effects chain — pedalboard-based signal processing pipeline.

Pipeline order: HighpassFilter → LowpassFilter → Reverb → Chorus → Compressor → Limiter

Two processing modes:
  process()       — batch (export): builds a fresh board, reset=True implied
  process_block() — streaming (live preview): reuses board with reset=False to
                    preserve delay-line state across callback blocks

Presets are stored in data/studio.db (SQLite).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "studio.db"


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fx_presets (
            id         INTEGER PRIMARY KEY,
            name       TEXT UNIQUE NOT NULL,
            data       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)


# ---------------------------------------------------------------------------
# EffectsChain
# ---------------------------------------------------------------------------

class EffectsChain:
    """Wraps a pedalboard Pedalboard with individually-togglable effects."""

    def __init__(self) -> None:
        # --- Highpass ---
        self.hp_enabled:    bool  = True
        self.hp_cutoff_hz:  float = 80.0

        # --- Lowpass ---
        self.lp_enabled:    bool  = True
        self.lp_cutoff_hz:  float = 16000.0

        # --- Reverb ---
        self.reverb_enabled:   bool  = True
        self.reverb_room_size: float = 0.3
        self.reverb_wet_level: float = 0.15
        self.reverb_dry_level: float = 0.85
        self.reverb_damping:   float = 0.5

        # --- Chorus ---
        self.chorus_enabled: bool  = True
        self.chorus_rate_hz: float = 0.5
        self.chorus_depth:   float = 0.1
        self.chorus_mix:     float = 0.1

        # --- Compressor ---
        self.comp_enabled:      bool  = True
        self.comp_threshold_db: float = -18.0
        self.comp_ratio:        float = 3.0
        self.comp_attack_ms:    float = 5.0
        self.comp_release_ms:   float = 100.0

        # --- Limiter ---
        self.limiter_enabled:      bool  = True
        self.limiter_threshold_db: float = -1.0
        self.limiter_release_ms:   float = 50.0

        self._dirty: bool = True
        self._board = None          # pedalboard.Pedalboard | None

    # ------------------------------------------------------------------
    # Board construction
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        import pedalboard as pb

        plugins = []
        if self.hp_enabled:
            plugins.append(pb.HighpassFilter(cutoff_frequency_hz=self.hp_cutoff_hz))
        if self.lp_enabled:
            plugins.append(pb.LowpassFilter(cutoff_frequency_hz=self.lp_cutoff_hz))
        if self.reverb_enabled:
            plugins.append(pb.Reverb(
                room_size=self.reverb_room_size,
                damping=self.reverb_damping,
                wet_level=self.reverb_wet_level,
                dry_level=self.reverb_dry_level,
            ))
        if self.chorus_enabled:
            plugins.append(pb.Chorus(
                rate_hz=self.chorus_rate_hz,
                depth=self.chorus_depth,
                mix=self.chorus_mix,
            ))
        if self.comp_enabled:
            plugins.append(pb.Compressor(
                threshold_db=self.comp_threshold_db,
                ratio=self.comp_ratio,
                attack_ms=self.comp_attack_ms,
                release_ms=self.comp_release_ms,
            ))
        if self.limiter_enabled:
            plugins.append(pb.Limiter(
                threshold_db=self.limiter_threshold_db,
                release_ms=self.limiter_release_ms,
            ))

        self._board = pb.Pedalboard(plugins)
        self._dirty = False

    def mark_dirty(self) -> None:
        """Signal that params changed — board will rebuild on next process call."""
        self._dirty = True

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Batch export: rebuild board fresh each call (preserves no state)."""
        self._rebuild()
        if not self._board:
            return audio
        return self._apply(audio, sr, reset=True)

    def process_block(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Streaming block: rebuilds only when dirty, preserves delay lines."""
        if self._dirty or self._board is None:
            self._rebuild()
        if not self._board:
            return audio
        return self._apply(audio, sr, reset=False)

    def reset_stream(self) -> None:
        """Force a rebuild on the next block (call on seek/stop)."""
        self._dirty = True

    def _apply(self, audio: np.ndarray, sr: int, reset: bool) -> np.ndarray:
        # Ensure float32, shape (n, ch)
        audio = np.asarray(audio, dtype=np.float32)
        squeezed = audio.ndim == 1
        if squeezed:
            audio = audio[:, np.newaxis]

        # pedalboard wants (channels, samples)
        x = np.ascontiguousarray(audio.T)
        y = self._board(x, sr, reset=reset)   # (channels, out_samples)
        result = y.T                           # (out_samples, channels)

        return result.squeeze(-1) if squeezed else result

    # ------------------------------------------------------------------
    # Preset serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "hp_enabled":           self.hp_enabled,
            "hp_cutoff_hz":         self.hp_cutoff_hz,
            "lp_enabled":           self.lp_enabled,
            "lp_cutoff_hz":         self.lp_cutoff_hz,
            "reverb_enabled":       self.reverb_enabled,
            "reverb_room_size":     self.reverb_room_size,
            "reverb_wet_level":     self.reverb_wet_level,
            "reverb_dry_level":     self.reverb_dry_level,
            "reverb_damping":       self.reverb_damping,
            "chorus_enabled":       self.chorus_enabled,
            "chorus_rate_hz":       self.chorus_rate_hz,
            "chorus_depth":         self.chorus_depth,
            "chorus_mix":           self.chorus_mix,
            "comp_enabled":         self.comp_enabled,
            "comp_threshold_db":    self.comp_threshold_db,
            "comp_ratio":           self.comp_ratio,
            "comp_attack_ms":       self.comp_attack_ms,
            "comp_release_ms":      self.comp_release_ms,
            "limiter_enabled":      self.limiter_enabled,
            "limiter_threshold_db": self.limiter_threshold_db,
            "limiter_release_ms":   self.limiter_release_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EffectsChain":
        chain = cls()
        for k, v in d.items():
            if hasattr(chain, k):
                setattr(chain, k, v)
        chain._dirty = True
        return chain

    # ------------------------------------------------------------------
    # SQLite preset storage
    # ------------------------------------------------------------------

    def save_preset(self, name: str) -> None:
        db = _db_path()
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db)) as conn:
            _ensure_table(conn)
            conn.execute(
                "INSERT OR REPLACE INTO fx_presets (name, data) VALUES (?, ?)",
                (name, json.dumps(self.to_dict())),
            )

    @staticmethod
    def list_presets() -> list[str]:
        db = _db_path()
        if not db.exists():
            return []
        try:
            with sqlite3.connect(str(db)) as conn:
                _ensure_table(conn)
                rows = conn.execute(
                    "SELECT name FROM fx_presets ORDER BY created_at"
                ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []

    @staticmethod
    def load_preset(name: str) -> Optional["EffectsChain"]:
        db = _db_path()
        if not db.exists():
            return None
        try:
            with sqlite3.connect(str(db)) as conn:
                _ensure_table(conn)
                row = conn.execute(
                    "SELECT data FROM fx_presets WHERE name = ?", (name,)
                ).fetchone()
            if row is None:
                return None
            return EffectsChain.from_dict(json.loads(row[0]))
        except Exception:
            return None

    @staticmethod
    def delete_preset(name: str) -> None:
        db = _db_path()
        if not db.exists():
            return
        with sqlite3.connect(str(db)) as conn:
            _ensure_table(conn)
            conn.execute("DELETE FROM fx_presets WHERE name = ?", (name,))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import numpy as np

    print("EffectsChain self-test …")
    sr = 44100
    t  = np.linspace(0, 2.0, sr * 2, endpoint=False, dtype=np.float32)
    mono = np.sin(2 * np.pi * 440 * t) * 0.5   # (N,)
    stereo = np.stack([mono, mono], axis=1)      # (N, 2)

    chain = EffectsChain()

    # Batch
    out = chain.process(stereo, sr)
    assert out.shape == stereo.shape, f"Shape mismatch: {out.shape} vs {stereo.shape}"
    print(f"  Batch  : {stereo.shape} -> {out.shape}  peak={np.abs(out).max():.4f}")

    # Streaming (simulate blocks)
    block = 2048
    chain.reset_stream()
    out_blocks = []
    for i in range(0, len(mono), block):
        chunk = stereo[i : i + block]
        out_blocks.append(chain.process_block(chunk, sr))
    streamed = np.concatenate(out_blocks, axis=0)
    print(f"  Stream : {stereo.shape} -> {streamed.shape}  peak={np.abs(streamed).max():.4f}")

    # Preset round-trip
    chain.save_preset("__test_preset__")
    names = EffectsChain.list_presets()
    assert "__test_preset__" in names, "Preset not saved"
    loaded = EffectsChain.load_preset("__test_preset__")
    assert loaded is not None
    assert abs(loaded.reverb_room_size - chain.reverb_room_size) < 1e-6
    EffectsChain.delete_preset("__test_preset__")
    print("  Preset save/load/delete: OK")

    print("Self-test passed.")
