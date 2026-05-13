"""AppState — single shared state object passed to all UI panels and engine modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from engine.effects.chain import EffectsChain
    from engine.composition.sequencer import Pattern


@dataclass
class AppState:
    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------
    is_playing: bool = False
    is_recording: bool = False
    playback_position: float = 0.0      # 0.0 to 1.0
    bpm: float = 120.0
    current_time_seconds: float = 0.0

    # ------------------------------------------------------------------
    # Loaded audio
    # ------------------------------------------------------------------
    audio_data: Optional[np.ndarray] = None
    sample_rate: int = 44100
    audio_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # Spatial
    # ------------------------------------------------------------------
    spatial_mode: str = "8d"            # "8d" or "stereo"
    rotation_path: str = "circle"       # circle, figure8, spiral, elevation, random
    rotation_speed: float = 0.15        # rotations per second
    rotation_angle: float = 0.0        # current azimuth in degrees (for viz)
    rotation_elevation: float = 0.0    # current elevation in degrees (for viz)

    # ------------------------------------------------------------------
    # Effects
    # ------------------------------------------------------------------
    effects_chain: Optional[object] = None  # EffectsChain — typed loosely to avoid import cycles

    # ------------------------------------------------------------------
    # Sequencer
    # ------------------------------------------------------------------
    pattern: Optional[object] = None    # Pattern dataclass, populated in Stage 5
    sequencer_playing: bool = False
    current_step: int = 0

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------
    project_name: str = "Untitled"
    project_path: Optional[Path] = None
    unsaved_changes: bool = False

    # ------------------------------------------------------------------
    # Spatial preview
    spatial_preview: bool = False           # True = real-time HRTF on playback

    # UI feedback
    # ------------------------------------------------------------------
    status_message: str = "Ready"
    processing_progress: float = 0.0   # 0.0 to 1.0, shown in progress bar
    is_processing: bool = False
