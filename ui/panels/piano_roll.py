"""
Piano Roll panel — collapsing header containing an interactive note grid.

Layout (inside the collapsing header):
  [toolbar: Import | Export | From Pattern | Play | Track selector | Zoom]
  [piano keys strip (fixed)] | [note grid drawlist (virtual-scroll)]
  [status text]

Interactions:
  Left-drag on empty grid  → create note (duration = drag width)
  Left-click on empty grid → create quarter note
  Right-click on note      → delete note
  Mouse wheel              → horizontal scroll
  Shift + mouse wheel      → horizontal zoom

Pitch range: A0 (MIDI 21) at bottom → C8 (MIDI 108) at top
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from ui.state import AppState
from engine.composition.midi import MidiData, MidiTrack, Note

# ---------------------------------------------------------------------------
# Grid constants
# ---------------------------------------------------------------------------
_KEY_H      = 5          # pixels per semitone row
_PIANO_W    = 30         # width of the piano keyboard strip
_GRID_VW    = 760        # visible width of the note grid
_DL_W       = _PIANO_W + _GRID_VW
_PITCH_MIN  = 21         # A0
_PITCH_MAX  = 108        # C8
_N_KEYS     = _PITCH_MAX - _PITCH_MIN + 1   # 88
_DL_H       = _N_KEYS * _KEY_H              # 440 px
_PX_PER_SEC = 80.0       # default horizontal zoom

_BLACK_PC   = {1, 3, 6, 8, 10}   # pitch classes that are black keys

# Tags
_DL_TAG     = "roll_dl"
_HANDLER    = "roll_handler"
_STATUS     = "roll_status"

# Colours
_C_GRID_BG    = (15, 18, 28, 255)
_C_WH_KEY     = (210, 210, 215, 255)
_C_BK_KEY     = (28,  32,  44, 255)
_C_ROW_BK     = (20,  23,  35, 255)   # black-key row tint
_C_ROW_WH     = (15,  18,  28, 255)
_C_ROW_C      = (22,  26,  40, 255)   # C-note row highlight
_C_BEAT       = (40,  48,  70, 160)
_C_BAR        = (55,  65,  95, 200)
_C_NOTE       = (80, 160, 240, 220)
_C_NOTE_SEL   = (255, 200, 60, 230)
_C_PREVIEW    = (80, 160, 240, 120)
_C_PLAYHEAD   = (255, 100,  60, 200)
_C_LABEL      = (130, 140, 170, 200)
_C_HEAD       = (175, 180, 215, 255)

# Module-level state
_midi_data: Optional[MidiData] = None
_scroll_x: float   = 0.0
_px_per_sec: float = _PX_PER_SEC
_sel_track: int    = 0
_dirty: bool       = True

# Drag-to-create state
_drag_start: Optional[tuple] = None   # (time, pitch) at drag origin
_drag_end_t: Optional[float] = None   # current drag end time

_state_ref:  Optional[AppState] = None
_engine_ref  = None                   # PlaybackEngine ref


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup(state: AppState, engine, parent: str | int) -> None:
    global _state_ref, _engine_ref, _midi_data, _dirty
    _state_ref  = state
    _engine_ref = engine
    _midi_data  = MidiData.empty(
        bpm=state.pattern.bpm if state.pattern else 120.0
    )

    with dpg.collapsing_header(
        label="Piano Roll", parent=parent, default_open=False
    ):
        _build_toolbar(state)
        dpg.add_spacer(height=4)
        dpg.add_drawlist(tag=_DL_TAG, width=_DL_W, height=_DL_H)
        dpg.add_spacer(height=2)
        dpg.add_text("", tag=_STATUS, color=_C_LABEL)

    _register_handlers()
    _dirty = True


def update(state: AppState) -> None:
    global _dirty
    if not dpg.does_item_exist(_DL_TAG):
        return
    if not dpg.is_item_visible(_DL_TAG):
        return
    if _dirty or _drag_start is not None:
        _redraw(state)
        _dirty = False


# ---------------------------------------------------------------------------
# Toolbar
# ---------------------------------------------------------------------------

def _build_toolbar(state: AppState) -> None:
    with dpg.group(horizontal=True):
        dpg.add_button(label="Import .mid", width=90,
                       callback=lambda: dpg.show_item("roll_open_dlg"))
        dpg.add_button(label="Export .mid", width=90,
                       callback=lambda: _export(state))
        dpg.add_button(label="From Pattern", width=95,
                       callback=lambda: _from_pattern(state))
        dpg.add_button(label="Play", width=52,
                       callback=lambda: _play(state))
        dpg.add_spacer(width=8)
        dpg.add_text("Track:", color=_C_LABEL)
        dpg.add_combo(
            tag="roll_track_combo",
            items=["Track 1"],
            default_value="Track 1",
            width=110,
            callback=lambda s, v: _set_track(v),
        )
        dpg.add_spacer(width=8)
        dpg.add_text("Zoom:", color=_C_LABEL)
        dpg.add_slider_float(
            tag="roll_zoom",
            min_value=20.0, max_value=400.0,
            default_value=_PX_PER_SEC,
            width=120, format="%.0f px/s",
            callback=_on_zoom,
        )

    # Hidden file dialog for import
    with dpg.file_dialog(
        tag="roll_open_dlg",
        directory_selector=False, show=False,
        callback=_on_file_selected,
        cancel_callback=lambda s, a: None,
        width=700, height=460,
    ):
        dpg.add_file_extension(".mid",  color=(100, 220, 100, 255), custom_text="[MIDI]")
        dpg.add_file_extension(".midi", color=(100, 220, 100, 255), custom_text="[MIDI]")
        dpg.add_file_extension(".*")


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _redraw(state: AppState) -> None:
    if not dpg.does_item_exist(_DL_TAG):
        return
    dpg.delete_item(_DL_TAG, children_only=True)

    _draw_row_backgrounds()
    _draw_grid_lines(state)
    _draw_piano_keys()
    _draw_notes()
    _draw_preview()
    _draw_playhead(state)


def _pitch_to_y(pitch: int) -> float:
    return (_PITCH_MAX - pitch) * _KEY_H


def _time_to_x(t: float) -> float:
    return _PIANO_W + t * _px_per_sec - _scroll_x


def _draw_row_backgrounds() -> None:
    for pitch in range(_PITCH_MIN, _PITCH_MAX + 1):
        y  = _pitch_to_y(pitch)
        pc = pitch % 12
        if pc in _BLACK_PC:
            fill = _C_ROW_BK
        elif pc == 0:
            fill = _C_ROW_C
        else:
            fill = _C_ROW_WH
        dpg.draw_rectangle(
            [_PIANO_W, y], [_DL_W, y + _KEY_H],
            fill=fill, color=(0, 0, 0, 0), parent=_DL_TAG,
        )


def _draw_grid_lines(state: AppState) -> None:
    bpm  = _midi_data.tempo if _midi_data else 120.0
    beat = 60.0 / bpm                        # quarter-note seconds
    bar  = beat * 4.0

    # Vertical beat/bar lines
    t_start = max(0.0, _scroll_x / _px_per_sec)
    t_end   = t_start + _GRID_VW / _px_per_sec + bar

    t = math.floor(t_start / beat) * beat
    while t <= t_end:
        x = _time_to_x(t)
        if _PIANO_W <= x <= _DL_W:
            is_bar = abs(t % bar) < 1e-6 or abs(t % bar - bar) < 1e-6
            color  = _C_BAR if is_bar else _C_BEAT
            dpg.draw_line([x, 0], [x, _DL_H], color=color, parent=_DL_TAG)
        t += beat


def _draw_piano_keys() -> None:
    for pitch in range(_PITCH_MIN, _PITCH_MAX + 1):
        y  = _pitch_to_y(pitch)
        pc = pitch % 12
        if pc in _BLACK_PC:
            fill  = _C_BK_KEY
            color = (18, 22, 34, 255)
        else:
            fill  = _C_WH_KEY
            color = (80, 90, 110, 200)
        dpg.draw_rectangle(
            [0, y + 1], [_PIANO_W - 1, y + _KEY_H - 1],
            fill=fill, color=color, parent=_DL_TAG,
        )
        # C note label
        if pc == 0:
            octave = (pitch // 12) - 1
            dpg.draw_text(
                [2, y + 1], f"C{octave}",
                color=(60, 80, 110, 200), size=9, parent=_DL_TAG,
            )


def _draw_notes() -> None:
    if _midi_data is None:
        return
    for t_idx, track in enumerate(_midi_data.tracks):
        for note in track.notes:
            x1 = _time_to_x(note.start)
            x2 = _time_to_x(note.end)
            if x2 < _PIANO_W or x1 > _DL_W:
                continue
            x1 = max(x1, _PIANO_W)
            y  = _pitch_to_y(note.pitch)
            alpha = int(180 + 40 * (note.velocity / 127))
            fill  = (80, 160, 240, alpha) if t_idx == 0 else (200, 100, 80, alpha)
            dpg.draw_rectangle(
                [x1 + 1, y + 1], [x2 - 1, y + _KEY_H - 1],
                fill=fill, color=(40, 80, 130, 200), parent=_DL_TAG,
            )


def _draw_preview() -> None:
    if _drag_start is None or _drag_end_t is None:
        return
    t_start, pitch = _drag_start
    t_end = max(_drag_end_t, t_start + 0.05)
    x1 = _time_to_x(t_start)
    x2 = _time_to_x(t_end)
    y  = _pitch_to_y(pitch)
    dpg.draw_rectangle(
        [max(x1, _PIANO_W) + 1, y + 1], [x2 - 1, y + _KEY_H - 1],
        fill=_C_PREVIEW, color=(80, 160, 240, 200), parent=_DL_TAG,
    )


def _draw_playhead(state: AppState) -> None:
    if not state.is_playing:
        return
    x = _time_to_x(state.current_time_seconds)
    if _PIANO_W <= x <= _DL_W:
        dpg.draw_line([x, 0], [x, _DL_H],
                      color=_C_PLAYHEAD, thickness=2, parent=_DL_TAG)


# ---------------------------------------------------------------------------
# Mouse handlers
# ---------------------------------------------------------------------------

def _register_handlers() -> None:
    if dpg.does_item_exist(_HANDLER):
        dpg.delete_item(_HANDLER)
    with dpg.handler_registry(tag=_HANDLER):
        dpg.add_mouse_drag_handler(
            button=dpg.mvMouseButton_Left,
            callback=_on_left_drag,
            threshold=2.0,
        )
        dpg.add_mouse_release_handler(
            button=dpg.mvMouseButton_Left,
            callback=_on_left_release,
        )
        dpg.add_mouse_click_handler(
            button=dpg.mvMouseButton_Left,
            callback=_on_left_click,
        )
        dpg.add_mouse_click_handler(
            button=dpg.mvMouseButton_Right,
            callback=_on_right_click,
        )
        dpg.add_mouse_wheel_handler(callback=_on_wheel)


def _screen_to_roll(mx: float, my: float) -> Optional[tuple]:
    """Convert screen coords to (time, pitch). Returns None if outside grid."""
    if not dpg.does_item_exist(_DL_TAG):
        return None
    pos = dpg.get_item_rect_min(_DL_TAG)
    rx  = mx - pos[0]
    ry  = my - pos[1]
    if rx < _PIANO_W or rx > _DL_W or ry < 0 or ry > _DL_H:
        return None
    t     = (rx - _PIANO_W + _scroll_x) / _px_per_sec
    pitch = _PITCH_MAX - int(ry / _KEY_H)
    pitch = max(_PITCH_MIN, min(_PITCH_MAX, pitch))
    return max(0.0, t), pitch


def _on_left_drag(sender, app_data) -> None:
    global _drag_start, _drag_end_t, _dirty
    _, dx, dy = app_data
    mx, my = dpg.get_mouse_pos()

    if _drag_start is None:
        # Reconstruct the press origin
        origin = _screen_to_roll(mx - dx, my - dy)
        if origin is not None:
            _drag_start = origin

    cur = _screen_to_roll(mx, my)
    if cur is not None:
        _drag_end_t = cur[0]
    _dirty = True


def _on_left_release(sender, app_data) -> None:
    global _drag_start, _drag_end_t, _dirty
    if _drag_start is not None and _drag_end_t is not None:
        t_start, pitch = _drag_start
        t_end   = max(_drag_end_t, t_start + 0.1)
        _add_note(pitch, t_start, t_end, 100)
    _drag_start = None
    _drag_end_t = None
    _dirty      = True


def _on_left_click(sender, app_data) -> None:
    """Single click (no drag) → place a quarter note."""
    global _dirty
    if _drag_start is not None:
        return   # was a drag, handled by release
    coords = _screen_to_roll(*dpg.get_mouse_pos())
    if coords is None:
        return
    t, pitch  = coords
    bpm       = _midi_data.tempo if _midi_data else 120.0
    beat      = 60.0 / bpm
    _add_note(pitch, t, t + beat, 100)
    _dirty = True


def _on_right_click(sender, app_data) -> None:
    global _dirty
    coords = _screen_to_roll(*dpg.get_mouse_pos())
    if coords is None or _midi_data is None:
        return
    t, pitch = coords
    for track in _midi_data.tracks:
        for i, note in enumerate(track.notes):
            if note.pitch == pitch and note.start <= t <= note.end:
                track.notes.pop(i)
                _dirty = True
                return


def _on_wheel(sender, app_data) -> None:
    global _scroll_x, _px_per_sec, _dirty
    delta = app_data
    keys  = dpg.get_app_configuration()  # unused — just check shift state
    if dpg.is_key_down(dpg.mvKey_Shift):
        # Zoom
        _px_per_sec = max(10.0, min(500.0, _px_per_sec + delta * 5.0))
        if dpg.does_item_exist("roll_zoom"):
            dpg.set_value("roll_zoom", _px_per_sec)
    else:
        # Scroll
        _scroll_x = max(0.0, _scroll_x - delta * 40.0)
    _dirty = True


def _on_zoom(sender, value) -> None:
    global _px_per_sec, _dirty
    _px_per_sec = value
    _dirty      = True


# ---------------------------------------------------------------------------
# Note manipulation
# ---------------------------------------------------------------------------

def _add_note(pitch: int, t_start: float, t_end: float, velocity: int) -> None:
    global _dirty
    if _midi_data is None:
        return
    if _sel_track >= len(_midi_data.tracks):
        return
    note = Note(pitch=pitch, start=t_start, end=t_end, velocity=velocity)
    _midi_data.tracks[_sel_track].notes.append(note)
    _midi_data.recalculate_duration()
    _dirty = True


def _set_track(label: str) -> None:
    global _sel_track, _dirty
    if _midi_data is None:
        return
    names = [t.name for t in _midi_data.tracks]
    if label in names:
        _sel_track = names.index(label)
        _dirty = True


def _refresh_track_combo() -> None:
    if _midi_data is None or not dpg.does_item_exist("roll_track_combo"):
        return
    names = [t.name for t in _midi_data.tracks]
    dpg.configure_item("roll_track_combo", items=names)
    if names:
        dpg.set_value("roll_track_combo", names[min(_sel_track, len(names) - 1)])


# ---------------------------------------------------------------------------
# File I/O callbacks
# ---------------------------------------------------------------------------

def _on_file_selected(sender, app_data: dict) -> None:
    global _midi_data, _sel_track, _dirty
    path_str = app_data.get("file_path_name", "")
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        _set_status(f"Not found: {path.name}")
        return
    try:
        from engine.composition.midi import load_midi
        _midi_data = load_midi(path)
        _sel_track = 0
        _refresh_track_combo()
        _set_status(
            f"Loaded: {path.name}  "
            f"({len(_midi_data.tracks)} tracks, "
            f"{sum(len(t.notes) for t in _midi_data.tracks)} notes, "
            f"{_midi_data.duration:.1f}s)"
        )
        _dirty = True
    except Exception as exc:
        _set_status(f"Load error: {exc}")


def _export(state: AppState) -> None:
    if _midi_data is None:
        _set_status("Nothing to export.")
        return
    path = Path("data/projects/export.mid")
    try:
        from engine.composition.midi import export_midi
        export_midi(_midi_data, path)
        _set_status(f"Exported: {path}")
    except Exception as exc:
        _set_status(f"Export error: {exc}")


def _from_pattern(state: AppState) -> None:
    global _midi_data, _sel_track, _dirty
    if state.pattern is None:
        _set_status("No pattern loaded.")
        return
    from engine.composition.midi import generate_midi_from_pattern
    _midi_data = generate_midi_from_pattern(state.pattern)
    _sel_track = 0
    _refresh_track_combo()
    _set_status(
        f"Converted pattern: {len(_midi_data.tracks)} tracks, "
        f"{sum(len(t.notes) for t in _midi_data.tracks)} notes"
    )
    _dirty = True


def _play(state: AppState) -> None:
    global _midi_data
    if _midi_data is None or _engine_ref is None:
        return
    _set_status("Rendering...")
    try:
        from engine.composition.midi import render_midi
        sf2_candidates = list(Path("data/soundfonts").glob("*.sf2"))
        sf2 = sf2_candidates[0] if sf2_candidates else None
        audio = render_midi(_midi_data, sf2)
        _engine_ref.load_audio_array(audio, 44100)
        _engine_ref.play()
        n = sum(len(t.notes) for t in _midi_data.tracks)
        _set_status(f"Playing {n} notes  ({audio.shape[0]/44100:.1f}s)")
    except Exception as exc:
        _set_status(f"Render error: {exc}")


def _set_status(msg: str) -> None:
    if dpg.does_item_exist(_STATUS):
        dpg.set_value(_STATUS, msg)
