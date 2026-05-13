"""Audio export — WAV (24-bit), FLAC, MP3."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def export_wav(audio: np.ndarray, sr: int, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="PCM_24")


def export_flac(audio: np.ndarray, sr: int, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, format="FLAC")


def export_mp3(audio: np.ndarray, sr: int, path: Path, bitrate: str = "320k") -> None:
    from engine.playback import _locate_ffmpeg_once
    _locate_ffmpeg_once()
    from pydub import AudioSegment

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    pcm = (audio * 32767.0).clip(-32768, 32767).astype(np.int16)
    channels = pcm.shape[1] if pcm.ndim > 1 else 1
    seg = AudioSegment(
        pcm.flatten().tobytes(),
        frame_rate=sr,
        sample_width=2,
        channels=channels,
    )
    seg.export(str(path), format="mp3", bitrate=bitrate)


def export(audio: np.ndarray, sr: int, path: Path) -> None:
    """Dispatch to the right exporter based on file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == ".wav":
        export_wav(audio, sr, path)
    elif suffix == ".flac":
        export_flac(audio, sr, path)
    elif suffix == ".mp3":
        export_mp3(audio, sr, path)
    else:
        raise ValueError(f"Unsupported export format: {suffix}")


# ------------------------------------------------------------------
# Self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    stereo = np.column_stack([
        np.sin(2 * np.pi * 440 * t) * 0.3,
        np.sin(2 * np.pi * 440 * t + 0.5) * 0.3,
    ]).astype(np.float32)

    out = Path(__file__).resolve().parent / "data/samples"
    export_wav(stereo, sr, out / "selftest.wav")
    export_flac(stereo, sr, out / "selftest.flac")
    print(f"WAV and FLAC written to {out}")
    print("test_export: PASSED")
