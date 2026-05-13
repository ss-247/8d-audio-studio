"""
Beat Sequencer panel.

Layout
------
  [BPM slider] [Play] [Stop] | [Save] [Load] [Clear]  <- top controls
  [Track labels & note]  [16-step grid drawlist]       <- main grid
  [status / backend text]

Grid colours
  OFF          dark slate
  ON           orange-amber
  PLAYING      bright yellow (current step during playback)
  ON+PLAYING   warm white
"""

from __future__ import annotations

import json
from pathlib import Path

import dearpygui.dearpygui as dpg

from ui.state import AppState
from engine.composition.sequencer import Pattern

# ---------------------------------------------------------------------------
# Grid geometry
# ---------------------------------------------------------------------------
_LABEL_W  = 88    # track name + note input column width
_STEP_W   = 36    # width of each step cell
_STEP_H   = 28    # height of each step cell
_N_TRACKS = 8
_N_STEPS  = 16
_GRID_W   = _LABEL_W + _N_STEPS * _STEP_W   # 664
_GRID_H   = _N_TRACKS * _STEP_H             # 224
_PAD      = 2

# Colours (RGBA)
_C_OFF     = (35,  42,  58, 255)
_C_ON      = (215, 140,  40, 255)
_C_PLAY    = (255, 240,  60, 255)
_C_ON_PLAY = (255, 255, 200, 255)
_C_BORDER  = (55,  65,  90, 200)
_C_LABEL   = (150, 155, 185, 255)
_C_HEAD    = (180, 185, 215, 255)
_C_BG      = (18,  22,  34, 255)

_DL_TAG    = "seq_dl"
_HANDLER   = "seq_click_handler"

# module-level caches (initialised in setup)
_cell_ids: list[list[int]] = []   # [track][step] = draw_rectangle item id
_note_tags: list[str]      = []   # "seq_note_{track}" for drag_int widgets
_state_ref: AppState | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup(state: AppState, parent: str | int) -> None:
    global _state_ref, _cell_ids, _note_tags
    _state_ref = state
    _cell_ids  = []
    _note_tags = []

    with dpg.group(parent=parent):
        dpg.add_text("Beat Sequencer", color=_C_HEAD)
        dpg.add_spacer(height=4)
        _build_controls(state)
        dpg.add_spacer(height=6)
        _build_grid(state)
        dpg.add_spacer(height=4)
        dpg.add_text("", tag="seq_status", color=(120, 160, 120, 255))

    _register_click_handler()


def update(state: AppState) -> None:
    """Called every frame — refresh step highlights and controls."""
    pattern = state.pattern
    if pattern is None or not _cell_ids:
        return

    current = state.current_step
    playing = state.sequencer_playing

    for t_idx, row in enumerate(_cell_ids):
        for s_idx, item_id in enumerate(row):
            vel  = pattern.tracks[t_idx].steps[s_idx].velocity
            is_c = playing and (s_idx == current)
            if is_c and vel > 0:
                fill = _C_ON_PLAY
            elif is_c:
                fill = _C_PLAY
            elif vel > 0:
                fill = _C_ON
            else:
                fill = _C_OFF
            dpg.configure_item(item_id, fill=fill)

    # BPM sync (engine may change it)
    if dpg.does_item_exist("seq_bpm") and state.pattern:
        pass   # BPM is only changed by the slider; no external source changes it


# ---------------------------------------------------------------------------
# Controls row
# ---------------------------------------------------------------------------

def _build_controls(state: AppState) -> None:
    with dpg.group(horizontal=True):
        dpg.add_text("BPM", color=_C_LABEL)
        dpg.add_slider_float(
            tag="seq_bpm",
            min_value=40.0, max_value=200.0,
            default_value=state.pattern.bpm if state.pattern else 120.0,
            width=160, format="%.0f",
            callback=lambda s, v: _set_bpm(v, state),
        )
        dpg.add_spacer(width=10)
        dpg.add_button(label=" Play ", tag="seq_play_btn",
                       callback=lambda: _play(state))
        dpg.add_button(label=" Stop ", tag="seq_stop_btn",
                       callback=lambda: _stop(state))
        dpg.add_spacer(width=16)
        dpg.add_button(label="Save", width=52,
                       callback=lambda: _save_pattern(state))
        dpg.add_button(label="Load", width=52,
                       callback=lambda: _load_pattern(state))
        dpg.add_button(label="Clear", width=52,
                       callback=lambda: _clear_pattern(state))
        dpg.add_input_text(
            tag="seq_file_path",
            default_value=str(Path("data/projects/pattern.json")),
            width=220,
        )


# ---------------------------------------------------------------------------
# Main grid
# ---------------------------------------------------------------------------

def _build_grid(state: AppState) -> None:
    pattern = state.pattern
    if pattern is None:
        dpg.add_text("No pattern loaded.", color=_C_LABEL)
        return

    with dpg.group(horizontal=True):
        # -- Left: track labels & note selectors --
        with dpg.child_window(
            width=_LABEL_W, height=_GRID_H,
            no_scrollbar=True, border=False,
        ):
            for t_idx, track in enumerate(pattern.tracks):
                tag = f"seq_note_{t_idx}"
                _note_tags.append(tag)
                with dpg.group(horizontal=False):
                    dpg.add_text(track.name, color=_C_LABEL)
                    dpg.add_drag_int(
                        tag=tag,
                        default_value=track.note,
                        min_value=0, max_value=127,
                        width=_LABEL_W - 8,
                        callback=lambda s, v, u=t_idx: _set_note(u, v, state),
                    )

        dpg.add_spacer(width=4)

        # -- Right: step grid drawlist --
        dl_w = _N_STEPS * _STEP_W
        dl_h = _GRID_H
        dpg.add_drawlist(tag=_DL_TAG, width=dl_w, height=dl_h)

        # Background
        dpg.draw_rectangle([0, 0], [dl_w, dl_h],
                           fill=_C_BG, color=_C_BG, parent=_DL_TAG)

        # Step number headers
        for s in range(_N_STEPS):
            x = s * _STEP_W + _STEP_W // 2 - 4
            num = str(s + 1)
            dpg.draw_text([x, 2], num, color=_C_LABEL, size=10, parent=_DL_TAG)

        # Beat dividers (every 4 steps)
        for b in range(1, 4):
            x = b * 4 * _STEP_W
            dpg.draw_line([x, 0], [x, dl_h],
                          color=(80, 90, 120, 120), thickness=1, parent=_DL_TAG)

        # Build cells
        y_offset = 12   # leave room for step numbers at top
        for t_idx, track in enumerate(pattern.tracks):
            row = []
            y = y_offset + t_idx * _STEP_H
            for s_idx in range(_N_STEPS):
                x   = s_idx * _STEP_W
                vel = track.steps[s_idx].velocity
                fill = _C_ON if vel > 0 else _C_OFF
                item_id = dpg.draw_rectangle(
                    [x + _PAD, y + _PAD],
                    [x + _STEP_W - _PAD, y + _STEP_H - _PAD],
                    fill=fill, color=_C_BORDER,
                    parent=_DL_TAG,
                )
                row.append(item_id)
            _cell_ids.append(row)


# ---------------------------------------------------------------------------
# Mouse click handler
# ---------------------------------------------------------------------------

def _register_click_handler() -> None:
    if dpg.does_item_exist(_HANDLER):
        dpg.delete_item(_HANDLER)
    with dpg.handler_registry(tag=_HANDLER):
        dpg.add_mouse_click_handler(
            button=dpg.mvMouseButton_Left,
            callback=_on_grid_left_click,
        )
        dpg.add_mouse_click_handler(
            button=dpg.mvMouseButton_Right,
            callback=_on_grid_right_click,
        )


def _grid_cell_from_mouse() -> tuple[int, int] | None:
    """Return (track_idx, step_idx) if mouse is over a step cell, else None."""
    if not dpg.does_item_exist(_DL_TAG):
        return None
    pos = dpg.get_item_rect_min(_DL_TAG)
    mx, my = dpg.get_mouse_pos()
    rx = mx - pos[0]
    ry = my - pos[1] - 12   # subtract header offset

    if rx < 0 or rx >= _N_STEPS * _STEP_W:
        return None
    if ry < 0 or ry >= _N_TRACKS * _STEP_H:
        return None

    s_idx = int(rx / _STEP_W)
    t_idx = int(ry / _STEP_H)
    return t_idx, s_idx


def _on_grid_left_click(sender, app_data) -> None:
    state = _state_ref
    if state is None or state.pattern is None:
        return
    cell = _grid_cell_from_mouse()
    if cell is None:
        return
    t_idx, s_idx = cell
    step = state.pattern.tracks[t_idx].steps[s_idx]
    step.velocity = 0 if step.velocity > 0 else 100
    state.unsaved_changes = True


def _on_grid_right_click(sender, app_data) -> None:
    """Right-click opens a velocity popup for the clicked step."""
    state = _state_ref
    if state is None or state.pattern is None:
        return
    cell = _grid_cell_from_mouse()
    if cell is None:
        return
    t_idx, s_idx = cell
    step = state.pattern.tracks[t_idx].steps[s_idx]

    tag = "seq_vel_popup"
    if dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    with dpg.window(
        tag=tag, popup=True, no_title_bar=True,
        width=160,
    ):
        dpg.add_text(
            f"Track {t_idx+1}, Step {s_idx+1}",
            color=_C_HEAD,
        )
        dpg.add_slider_int(
            label="Velocity",
            default_value=step.velocity if step.velocity > 0 else 100,
            min_value=1, max_value=127,
            width=140,
            callback=lambda s, v: _set_velocity(t_idx, s_idx, v, state),
        )
        dpg.add_button(
            label="Clear step",
            callback=lambda: (_set_velocity(t_idx, s_idx, 0, state),
                              dpg.delete_item(tag)),
        )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _set_bpm(value: float, state: AppState) -> None:
    if state.pattern:
        state.pattern.bpm = value
    seq = getattr(state, "_sequencer", None)
    if seq is not None:
        seq.bpm = value


def _set_note(track_idx: int, value: int, state: AppState) -> None:
    if state.pattern:
        state.pattern.tracks[track_idx].note = value


def _set_velocity(t_idx: int, s_idx: int, vel: int, state: AppState) -> None:
    if state.pattern:
        state.pattern.tracks[t_idx].steps[s_idx].velocity = vel
    state.unsaved_changes = True


def _play(state: AppState) -> None:
    seq = getattr(state, "_sequencer", None)
    if seq is not None and not seq.is_playing:
        seq.start()
        state.sequencer_playing = True
        dpg.set_value("seq_status", "Playing...")


def _stop(state: AppState) -> None:
    seq = getattr(state, "_sequencer", None)
    if seq is not None:
        seq.stop()
    state.sequencer_playing = False
    state.current_step      = 0
    dpg.set_value("seq_status", "Stopped")


def _save_pattern(state: AppState) -> None:
    if state.pattern is None:
        return
    path_str = dpg.get_value("seq_file_path").strip()
    if not path_str:
        path_str = "data/projects/pattern.json"
    path = Path(path_str)
    try:
        state.pattern.save(path)
        state.unsaved_changes = False
        dpg.set_value("seq_status", f"Saved: {path.name}")
    except Exception as exc:
        dpg.set_value("seq_status", f"Save failed: {exc}")


def _load_pattern(state: AppState) -> None:
    path_str = dpg.get_value("seq_file_path").strip()
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        dpg.set_value("seq_status", f"Not found: {path}")
        return
    try:
        loaded = Pattern.load(path)
        state.pattern = loaded
        if dpg.does_item_exist("seq_bpm"):
            dpg.set_value("seq_bpm", loaded.bpm)
        _sync_note_widgets(loaded)
        _reset_cells(loaded)
        state.unsaved_changes = False
        dpg.set_value("seq_status", f"Loaded: {path.name}")
    except Exception as exc:
        dpg.set_value("seq_status", f"Load failed: {exc}")


def _clear_pattern(state: AppState) -> None:
    if state.pattern is None:
        return
    for track in state.pattern.tracks:
        for step in track.steps:
            step.velocity = 0
    state.unsaved_changes = True


def _sync_note_widgets(pattern) -> None:
    for t_idx, track in enumerate(pattern.tracks):
        tag = f"seq_note_{t_idx}"
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, track.note)


def _reset_cells(pattern) -> None:
    for t_idx, row in enumerate(_cell_ids):
        for s_idx, item_id in enumerate(row):
            vel  = pattern.tracks[t_idx].steps[s_idx].velocity if t_idx < len(pattern.tracks) else 0
            fill = _C_ON if vel > 0 else _C_OFF
            dpg.configure_item(item_id, fill=fill)


