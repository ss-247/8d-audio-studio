"""
Waveform display panel.

Draws the audio waveform as a min/max column chart into a Dear PyGui drawlist.
A float slider below acts as both a scrubber indicator and a seek control.
The drawlist also accepts mouse clicks to seek.
"""

from __future__ import annotations

import numpy as np
import dearpygui.dearpygui as dpg

from ui.state import AppState
from engine.playback import PlaybackEngine

# Internal state (module-level, only one waveform panel exists)
_draw_w: int = 1200
_draw_h: int = 160

_DL_TAG = "waveform_dl"
_SCRUBBER_TAG = "scrubber"
_PLACEHOLDER_TAG = "waveform_placeholder"
_CURSOR_TAG = "waveform_cursor"


def setup(state: AppState, engine: PlaybackEngine, parent: str | int) -> None:
    global _draw_w
    _draw_w = max(400, dpg.get_viewport_client_width() - 48)

    with dpg.child_window(
        parent=parent,
        tag="waveform_child",
        height=_draw_h + 60,
        no_scrollbar=True,
        border=False,
    ):
        dpg.add_drawlist(width=_draw_w, height=_draw_h, tag=_DL_TAG)

        # Initial background + placeholder text
        dpg.draw_rectangle(
            [0, 0], [_draw_w, _draw_h],
            fill=(20, 20, 28, 255),
            color=(45, 45, 60, 255),
            parent=_DL_TAG,
        )
        dpg.draw_text(
            [_draw_w // 2 - 180, _draw_h // 2 - 8],
            "No audio loaded — File > Open Audio File",
            color=(80, 80, 100, 255),
            size=16,
            parent=_DL_TAG,
            tag=_PLACEHOLDER_TAG,
        )

        dpg.add_spacer(height=6)
        dpg.add_slider_float(
            tag=_SCRUBBER_TAG,
            min_value=0.0,
            max_value=1.0,
            default_value=0.0,
            width=-1,
            format="",
            callback=lambda s, v: _on_scrub(v, engine, state),
        )

    # Click-to-seek on the drawlist
    with dpg.item_handler_registry(tag="wf_handler"):
        dpg.add_item_clicked_handler(
            callback=lambda s, a: _on_waveform_click(engine, state)
        )
    dpg.bind_item_handler_registry(_DL_TAG, "wf_handler")


def draw_waveform(audio: np.ndarray, sr: int) -> None:
    """Rebuild the waveform graphic.  Call after loading new audio."""
    dpg.delete_item(_DL_TAG, children_only=True)

    # Background
    dpg.draw_rectangle(
        [0, 0], [_draw_w, _draw_h],
        fill=(20, 20, 28, 255),
        color=(45, 45, 60, 255),
        parent=_DL_TAG,
    )

    # Mix to mono, normalize
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio.flatten()
    peak = np.abs(mono).max()
    if peak > 0:
        mono = mono / peak

    # Build per-pixel min/max buckets
    n = len(mono)
    buckets = _draw_w
    center_y = _draw_h / 2.0
    half = center_y * 0.88

    edges = np.linspace(0, n, buckets + 1, dtype=int)
    for i in range(buckets):
        chunk = mono[edges[i] : edges[i + 1]]
        if len(chunk) == 0:
            continue
        lo = float(chunk.min())
        hi = float(chunk.max())
        y1 = center_y - hi * half
        y2 = center_y - lo * half
        if y2 - y1 < 1.0:
            y2 = y1 + 1.0
        dpg.draw_line(
            [i, y1], [i, y2],
            color=(70, 120, 220, 210),
            parent=_DL_TAG,
        )

    # Centre line
    dpg.draw_line(
        [0, center_y], [_draw_w, center_y],
        color=(50, 55, 85, 160),
        parent=_DL_TAG,
    )

    # Playback cursor (starts at x=0)
    dpg.draw_line(
        [0, 0], [0, _draw_h],
        color=(255, 200, 60, 200),
        parent=_DL_TAG,
        tag=_CURSOR_TAG,
    )


def update(state: AppState) -> None:
    """Called every frame — moves scrubber and cursor to match playback position."""
    pos = state.playback_position
    dpg.set_value(_SCRUBBER_TAG, pos)

    # Move cursor line if it exists
    if dpg.does_item_exist(_CURSOR_TAG):
        x = int(pos * _draw_w)
        dpg.configure_item(_CURSOR_TAG, p1=[x, 0], p2=[x, _draw_h])


def _on_scrub(value: float, engine: PlaybackEngine, state: AppState) -> None:
    engine.seek(value)
    state.playback_position = value


def _on_waveform_click(engine: PlaybackEngine, state: AppState) -> None:
    mouse_x, _ = dpg.get_mouse_pos(local=False)
    rect = dpg.get_item_rect_min(_DL_TAG)
    rel_x = max(0.0, mouse_x - rect[0])
    position = min(1.0, rel_x / _draw_w)
    engine.seek(position)
    state.playback_position = position
