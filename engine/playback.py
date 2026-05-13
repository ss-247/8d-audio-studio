"""
Audio loading and real-time playback engine.

Supports two output modes set before calling play():
  - Passthrough  : audio copied straight to the output stream
  - Spatial preview : each callback block is HRTF-convolved using overlap-add,
                      so the 8D effect is heard live without pre-rendering.

All control flags are plain Python attributes — the GIL makes single-attribute
reads/writes atomic, so no lock is needed in the audio-callback hot path.
A lock guards stream open/close only.
"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import fftconvolve

# ------------------------------------------------------------------
# FFmpeg location helper (runs once per process)
# ------------------------------------------------------------------

_ffmpeg_located = False


def _locate_ffmpeg_once() -> None:
    """Refresh PATH from the Windows registry once so pydub finds FFmpeg
    even when installed after this terminal session started."""
    global _ffmpeg_located
    if _ffmpeg_located:
        return
    _ffmpeg_located = True

    if shutil.which("ffmpeg"):
        return

    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ) as k:
            machine = winreg.QueryValueEx(k, "PATH")[0]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
            try:
                user = winreg.QueryValueEx(k, "PATH")[0]
            except FileNotFoundError:
                user = ""
        os.environ["PATH"] = machine + os.pathsep + user
    except Exception:
        pass


# ------------------------------------------------------------------
# PlaybackEngine
# ------------------------------------------------------------------

class PlaybackEngine:
    # Block size used for the output stream.
    # Must be larger than HRTF IR length (512) for efficient overlap-add.
    _BLOCKSIZE = 2048

    def __init__(self) -> None:
        self._audio: Optional[np.ndarray] = None   # float32 (N, ch)
        self._sr: int = 44100
        self._position: int = 0
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._stream: Optional[sd.OutputStream] = None
        self._stream_lock = threading.Lock()

        # Spatial preview state (set via enable_spatial / disable_spatial)
        self._spatial: bool = False
        self._hrtf = None           # HRTFDatabase | None
        self._rot_path = None       # RotationPath | None
        self._tail_l: np.ndarray = np.zeros(0, dtype=np.float32)
        self._tail_r: np.ndarray = np.zeros(0, dtype=np.float32)

    # ------------------------------------------------------------------
    # Spatial preview control
    # ------------------------------------------------------------------

    def enable_spatial(self, hrtf_db, rotation_path) -> None:
        """Switch to real-time HRTF convolution on the next Play."""
        self._hrtf     = hrtf_db
        self._rot_path = rotation_path
        self._spatial  = True
        ir_len = hrtf_db.ir_length
        self._tail_l = np.zeros(ir_len - 1, dtype=np.float32)
        self._tail_r = np.zeros(ir_len - 1, dtype=np.float32)

    def disable_spatial(self) -> None:
        self._spatial = False

    def update_rotation_path(self, rotation_path) -> None:
        """Hot-swap the rotation path mid-playback (GIL-safe reference swap)."""
        self._rot_path = rotation_path
        if self._hrtf is not None:
            ir_len = self._hrtf.ir_length
            self._tail_l = np.zeros(ir_len - 1, dtype=np.float32)
            self._tail_r = np.zeros(ir_len - 1, dtype=np.float32)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_audio(self, path: Path) -> Tuple[np.ndarray, int]:
        path = Path(path)
        suffix = path.suffix.lower()

        if suffix in ('.wav', '.flac', '.ogg', '.aiff', '.aif'):
            audio, sr = sf.read(str(path), dtype='float32', always_2d=True)
        elif suffix in ('.mp3', '.m4a', '.aac', '.wma'):
            try:
                _locate_ffmpeg_once()
                from pydub import AudioSegment
                seg = AudioSegment.from_file(str(path))
            except FileNotFoundError:
                raise RuntimeError(
                    "FFmpeg not found. Install: winget install --id=Gyan.FFmpeg -e"
                )
            seg = seg.set_frame_rate(44100)
            sr  = seg.frame_rate
            raw = np.array(seg.get_array_of_samples(), dtype=np.float32)
            raw /= 2 ** (seg.sample_width * 8 - 1)
            audio = raw.reshape(-1, seg.channels)
        else:
            raise ValueError(f"Unsupported format: {suffix}")

        self.stop()
        self._audio    = audio
        self._sr       = int(sr)
        self._position = 0
        return audio, int(sr)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self) -> None:
        if self._audio is None:
            return
        if self._is_paused:
            self._is_paused = False
            return
        if self._is_playing:
            return
        self._close_stream()

        # Always open a 2-channel stream so spatial/passthrough can switch
        # without reopening.
        stream = sd.OutputStream(
            samplerate=self._sr,
            channels=2,
            dtype='float32',
            callback=self._audio_callback,
            finished_callback=self._on_stream_finished,
            blocksize=self._BLOCKSIZE,
        )
        with self._stream_lock:
            self._stream = stream
        self._is_playing = True
        self._is_paused  = False
        stream.start()

    def pause(self) -> None:
        if self._is_playing:
            self._is_paused = not self._is_paused

    def stop(self) -> None:
        self._close_stream()
        self._position = 0

    def seek(self, position: float) -> None:
        if self._audio is None:
            return
        self._position = max(0, min(int(position * len(self._audio)), len(self._audio) - 1))
        # Reset overlap-add tails on seek to avoid glitches
        if self._hrtf is not None:
            ir_len = self._hrtf.ir_length
            self._tail_l = np.zeros(ir_len - 1, dtype=np.float32)
            self._tail_r = np.zeros(ir_len - 1, dtype=np.float32)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    @property
    def playback_position(self) -> float:
        if self._audio is None or len(self._audio) == 0:
            return 0.0
        return self._position / len(self._audio)

    @property
    def current_time_seconds(self) -> float:
        return self._position / self._sr if self._sr > 0 else 0.0

    @property
    def total_duration(self) -> float:
        return len(self._audio) / self._sr if self._audio is not None else 0.0

    @property
    def is_playing(self) -> bool:
        return self._is_playing and not self._is_paused

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def has_audio(self) -> bool:
        return self._audio is not None

    # ------------------------------------------------------------------
    # Audio callback
    # ------------------------------------------------------------------

    def _audio_callback(self, outdata: np.ndarray, frames: int, time, status) -> None:
        audio = self._audio
        pos   = self._position

        if audio is None or not self._is_playing or self._is_paused:
            outdata[:] = 0
            return

        remaining = len(audio) - pos
        if remaining <= 0:
            outdata[:] = 0
            raise sd.CallbackStop()

        n     = min(frames, remaining)
        chunk = audio[pos : pos + n]   # (n, src_channels)

        if self._spatial and self._hrtf is not None and self._rot_path is not None:
            self._fill_spatial(outdata, chunk, frames, n, pos)
        else:
            self._fill_passthrough(outdata, chunk, frames, n)

        self._position = pos + n

    def _fill_passthrough(
        self, outdata: np.ndarray, chunk: np.ndarray, frames: int, n: int
    ) -> None:
        if chunk.ndim > 1 and chunk.shape[1] >= 2:
            outdata[:n]  = chunk[:, :2]
        else:
            mono = chunk.flatten() if chunk.ndim > 1 else chunk
            outdata[:n, 0] = mono
            outdata[:n, 1] = mono
        if n < frames:
            outdata[n:] = 0

    def _fill_spatial(
        self,
        outdata: np.ndarray,
        chunk: np.ndarray,
        frames: int,
        n: int,
        pos: int,
    ) -> None:
        hrtf     = self._hrtf
        rot_path = self._rot_path

        # Mix to mono, pad to full block
        mono = chunk.mean(axis=1) if chunk.ndim > 1 else chunk.flatten()
        if len(mono) < frames:
            mono = np.pad(mono, (0, frames - len(mono)))

        # Rotation angle at block centre
        t = (pos + frames * 0.5) / self._sr
        az, el = rot_path.get_angle(t)
        hrir_l, hrir_r = hrtf.get_hrir(az, el)

        # Convolve: output length = frames + ir_len − 1
        lc = fftconvolve(mono, hrir_l).astype(np.float32)
        rc = fftconvolve(mono, hrir_r).astype(np.float32)

        # Overlap-add: mix in tail from previous block
        tail_len = len(self._tail_l)
        lc[:tail_len] += self._tail_l
        rc[:tail_len] += self._tail_r

        # Save tail for next block
        self._tail_l = lc[frames : frames + tail_len].copy()
        self._tail_r = rc[frames : frames + tail_len].copy()

        outdata[:, 0] = lc[:frames]
        outdata[:, 1] = rc[:frames]

    # ------------------------------------------------------------------
    # Stream lifecycle
    # ------------------------------------------------------------------

    def _on_stream_finished(self) -> None:
        self._is_playing = False
        self._is_paused  = False
        self._position   = 0

    def _close_stream(self) -> None:
        with self._stream_lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._is_playing = False
        self._is_paused  = False


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------

if __name__ == "__main__":
    import time

    print("PlaybackEngine self-test — 440 Hz sine, 2 seconds, passthrough.")
    sr       = 44100
    t        = np.linspace(0, 2.0, sr * 2, endpoint=False)
    audio    = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32).reshape(-1, 1)
    engine   = PlaybackEngine()
    engine._audio = audio
    engine._sr    = sr
    engine.play()
    for _ in range(22):
        time.sleep(0.1)
        print(f"\r  t={engine.current_time_seconds:.2f}s", end="")
        if not engine._is_playing:
            break
    print("\nSelf-test passed.")
    engine.stop()
