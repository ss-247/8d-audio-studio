"""
Spatial visualizer panel.

Left side: animated top-down head view with rotating source dot.
Right side: mode/path/speed controls + Process & Export button.
"""

from __future__ import annotations

import math

import dearpygui.dearpygui as dpg

from ui.state import AppState
from engine.spatial.rotation import PATH_LABELS, PATH_KEYS

_DL_TAG   = "spatial_viz_dl"
_DOT_TAG  = "spatial_dot"
_W = _H   = 200
_CX = _CY = 100.0
_R        = 76.0   # orbit radius


def setup(state: AppState, parent: str | int) -> None:
    with dpg.group(horizontal=True, parent=parent):
        # ---- animated circle ----
        with dpg.group():
            dpg.add_drawlist(width=_W, height=_H, tag=_DL_TAG)
            _draw_static_bg()

        dpg.add_spacer(width=20)

        # ---- controls ----
        with dpg.group():
            dpg.add_spacer(height=4)
            dpg.add_text("Spatial Mode", color=(155, 155, 185, 255))
            dpg.add_radio_button(
                items=["8D Binaural", "Stereo Wide"],
                tag="spatial_mode_radio",
                default_value="8D Binaural",
                horizontal=True,
                callback=lambda s, v: _set_mode(v, state),
            )

            dpg.add_spacer(height=10)
            dpg.add_text("Rotation Path", color=(155, 155, 185, 255))
            dpg.add_combo(
                items=PATH_LABELS,
                default_value=PATH_LABELS[0],
                tag="path_combo",
                width=190,
                callback=lambda s, v: _set_path(v, state),
            )

            dpg.add_spacer(height=8)
            dpg.add_text("Speed (rot/s)", color=(155, 155, 185, 255))
            dpg.add_slider_float(
                tag="speed_slider",
                min_value=0.05,
                max_value=1.0,
                default_value=state.rotation_speed,
                width=190,
                format="%.2f",
                callback=lambda s, v: setattr(state, "rotation_speed", v),
            )

            dpg.add_spacer(height=12)
            dpg.add_checkbox(
                label=" Live Preview (hear 8D now)",
                tag="spatial_preview_check",
                default_value=False,
                callback=lambda s, v: _on_preview_toggle(v, state),
            )
            dpg.add_spacer(height=10)
            dpg.add_button(
                label="  Process & Export  ",
                tag="btn_process",
                width=190,
                callback=lambda: dpg.show_item("export_file_dialog"),
            )

            dpg.add_spacer(height=6)
            dpg.add_progress_bar(tag="progress_bar", default_value=0.0, width=190)
            dpg.add_spacer(height=4)
            dpg.add_text("", tag="export_status", color=(140, 210, 140, 255))


def update(state: AppState) -> None:
    """Move the dot to match AppState.rotation_angle every frame."""
    az_rad = math.radians(state.rotation_angle)
    el_norm = max(-1.0, min(1.0, state.rotation_elevation / 90.0))

    x = _CX + _R * math.sin(az_rad)
    y = _CY - _R * math.cos(az_rad)

    radius = max(4.0, 8.0 - abs(el_norm) * 3.0)
    alpha  = int(160 + 80 * (1.0 - abs(el_norm)))

    if dpg.does_item_exist(_DOT_TAG):
        dpg.configure_item(
            _DOT_TAG,
            center=[x, y],
            radius=radius,
            fill=[255, 175, 50, alpha],
            color=[255, 215, 100, 230],
        )

    dpg.set_value("progress_bar", state.processing_progress)


def _draw_static_bg() -> None:
    dpg.delete_item(_DL_TAG, children_only=True)

    # Background
    dpg.draw_rectangle([0, 0], [_W, _H],
                       fill=(18, 18, 26, 255), color=(38, 38, 55, 255),
                       parent=_DL_TAG)
    # Orbit ring
    dpg.draw_circle([_CX, _CY], _R,
                    color=(48, 58, 88, 210), thickness=1, parent=_DL_TAG)
    # Head
    dpg.draw_circle([_CX, _CY], 13,
                    fill=(38, 48, 78, 255), color=(65, 85, 135, 255),
                    parent=_DL_TAG)
    # Cross-hairs
    dpg.draw_line([_CX, _CY - _R - 5], [_CX, _CY + _R + 5],
                  color=(38, 48, 70, 110), parent=_DL_TAG)
    dpg.draw_line([_CX - _R - 5, _CY], [_CX + _R + 5, _CY],
                  color=(38, 48, 70, 110), parent=_DL_TAG)
    # "F" front marker
    dpg.draw_text([_CX - 5, 4], "F", color=(75, 88, 118, 200),
                  size=13, parent=_DL_TAG)
    # Dot — starts at front (az=0)
    dpg.draw_circle([_CX, _CY - _R], 7,
                    fill=[255, 175, 50, 220],
                    color=[255, 215, 100, 255],
                    parent=_DL_TAG,
                    tag=_DOT_TAG)


def _set_mode(label: str, state: AppState) -> None:
    state.spatial_mode = "8d" if "8D" in label else "stereo"


def _set_path(label: str, state: AppState) -> None:
    if label in PATH_LABELS:
        state.rotation_path = PATH_KEYS[PATH_LABELS.index(label)]


def _on_preview_toggle(enabled: bool, state: AppState) -> None:
    state.spatial_preview = enabled
