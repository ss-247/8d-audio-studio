"""Transport panel — Play / Pause / Stop, time display, BPM."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from ui.state import AppState
from engine.playback import PlaybackEngine


def setup(state: AppState, engine: PlaybackEngine, parent: str | int) -> None:
    with dpg.group(horizontal=True, parent=parent, tag="transport_group"):
        dpg.add_button(
            label="  Play  ",
            tag="btn_play",
            width=90,
            callback=lambda: _on_play(state, engine),
        )
        dpg.add_button(
            label=" Pause ",
            tag="btn_pause",
            width=90,
            callback=lambda: _on_pause(state, engine),
        )
        dpg.add_button(
            label="  Stop  ",
            tag="btn_stop",
            width=90,
            callback=lambda: _on_stop(state, engine),
        )
        dpg.add_spacer(width=24)
        dpg.add_text("00:00 / 00:00", tag="time_display", color=(200, 200, 220, 255))
        dpg.add_spacer(width=24)
        dpg.add_text(f"BPM: {state.bpm:.0f}", tag="bpm_display", color=(140, 140, 165, 255))
        dpg.add_spacer(width=24)
        dpg.add_text(state.status_message, tag="status_display", color=(110, 200, 110, 255))


def update(state: AppState, engine: PlaybackEngine) -> None:
    cur = engine.current_time_seconds
    tot = engine.total_duration
    mc, sc = divmod(int(cur), 60)
    mt, st = divmod(int(tot), 60)
    dpg.set_value("time_display", f"{mc:02d}:{sc:02d} / {mt:02d}:{st:02d}")
    dpg.set_value("status_display", state.status_message)
    dpg.set_value("bpm_display", f"BPM: {state.bpm:.0f}")



def _on_play(state: AppState, engine: PlaybackEngine) -> None:
    engine.play()
    state.is_playing = True
    state.status_message = "Playing"


def _on_pause(state: AppState, engine: PlaybackEngine) -> None:
    engine.pause()
    if engine.is_paused:
        state.is_playing = False
        state.status_message = "Paused"
    else:
        state.is_playing = True
        state.status_message = "Playing"


def _on_stop(state: AppState, engine: PlaybackEngine) -> None:
    engine.stop()
    state.is_playing = False
    state.playback_position = 0.0
    state.status_message = "Stopped"
