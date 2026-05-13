"""
Effects Chain panel.

Horizontal row of six compact cards:
  [HP Filter] [LP Filter] [Reverb] [Chorus] [Compressor] [Limiter]

Below the cards: preset name input, Save / Load / Delete buttons.
"""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from ui.state import AppState

_CARD_W  = 148
_CARD_H  = 148
_LABEL_C = (155, 155, 185, 255)
_HEAD_C  = (190, 190, 220, 255)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup(state: AppState, parent: str | int) -> None:
    with dpg.group(parent=parent):
        dpg.add_text("Effects Chain", color=_HEAD_C)
        dpg.add_spacer(height=4)

        with dpg.group(horizontal=True):
            _hp_card(state)
            dpg.add_spacer(width=4)
            _lp_card(state)
            dpg.add_spacer(width=4)
            _reverb_card(state)
            dpg.add_spacer(width=4)
            _chorus_card(state)
            dpg.add_spacer(width=4)
            _comp_card(state)
            dpg.add_spacer(width=4)
            _limiter_card(state)

        dpg.add_spacer(height=6)
        _preset_row(state)


def update(state: AppState) -> None:
    """Called every frame — nothing to poll, UI is fully callback-driven."""
    pass


# ---------------------------------------------------------------------------
# Individual cards
# ---------------------------------------------------------------------------

def _hp_card(state: AppState) -> None:
    chain = state.effects_chain
    with dpg.child_window(width=_CARD_W, height=_CARD_H, border=True):
        dpg.add_checkbox(
            label=" HP Filter",
            tag="fx_hp_en",
            default_value=chain.hp_enabled if chain else True,
            callback=lambda s, v: _set(chain, "hp_enabled", v),
        )
        dpg.add_spacer(height=4)
        dpg.add_text("Cutoff Hz", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_hp_cutoff",
            min_value=20.0, max_value=500.0,
            default_value=chain.hp_cutoff_hz if chain else 80.0,
            width=_CARD_W - 14, format="%.0f",
            callback=lambda s, v: _set(chain, "hp_cutoff_hz", v),
        )


def _lp_card(state: AppState) -> None:
    chain = state.effects_chain
    with dpg.child_window(width=_CARD_W, height=_CARD_H, border=True):
        dpg.add_checkbox(
            label=" LP Filter",
            tag="fx_lp_en",
            default_value=chain.lp_enabled if chain else True,
            callback=lambda s, v: _set(chain, "lp_enabled", v),
        )
        dpg.add_spacer(height=4)
        dpg.add_text("Cutoff Hz", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_lp_cutoff",
            min_value=2000.0, max_value=20000.0,
            default_value=chain.lp_cutoff_hz if chain else 16000.0,
            width=_CARD_W - 14, format="%.0f",
            callback=lambda s, v: _set(chain, "lp_cutoff_hz", v),
        )


def _reverb_card(state: AppState) -> None:
    chain = state.effects_chain
    with dpg.child_window(width=_CARD_W, height=_CARD_H, border=True):
        dpg.add_checkbox(
            label=" Reverb",
            tag="fx_rev_en",
            default_value=chain.reverb_enabled if chain else True,
            callback=lambda s, v: _set(chain, "reverb_enabled", v),
        )
        dpg.add_spacer(height=4)
        dpg.add_text("Room Size", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_rev_room",
            min_value=0.0, max_value=1.0,
            default_value=chain.reverb_room_size if chain else 0.3,
            width=_CARD_W - 14, format="%.2f",
            callback=lambda s, v: _set(chain, "reverb_room_size", v),
        )
        dpg.add_text("Wet", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_rev_wet",
            min_value=0.0, max_value=1.0,
            default_value=chain.reverb_wet_level if chain else 0.15,
            width=_CARD_W - 14, format="%.2f",
            callback=lambda s, v: _set(chain, "reverb_wet_level", v),
        )


def _chorus_card(state: AppState) -> None:
    chain = state.effects_chain
    with dpg.child_window(width=_CARD_W, height=_CARD_H, border=True):
        dpg.add_checkbox(
            label=" Chorus",
            tag="fx_cho_en",
            default_value=chain.chorus_enabled if chain else True,
            callback=lambda s, v: _set(chain, "chorus_enabled", v),
        )
        dpg.add_spacer(height=4)
        dpg.add_text("Rate Hz", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_cho_rate",
            min_value=0.1, max_value=5.0,
            default_value=chain.chorus_rate_hz if chain else 0.5,
            width=_CARD_W - 14, format="%.2f",
            callback=lambda s, v: _set(chain, "chorus_rate_hz", v),
        )
        dpg.add_text("Depth", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_cho_depth",
            min_value=0.0, max_value=1.0,
            default_value=chain.chorus_depth if chain else 0.1,
            width=_CARD_W - 14, format="%.2f",
            callback=lambda s, v: _set(chain, "chorus_depth", v),
        )


def _comp_card(state: AppState) -> None:
    chain = state.effects_chain
    with dpg.child_window(width=_CARD_W, height=_CARD_H, border=True):
        dpg.add_checkbox(
            label=" Compressor",
            tag="fx_comp_en",
            default_value=chain.comp_enabled if chain else True,
            callback=lambda s, v: _set(chain, "comp_enabled", v),
        )
        dpg.add_spacer(height=4)
        dpg.add_text("Threshold dB", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_comp_thresh",
            min_value=-40.0, max_value=0.0,
            default_value=chain.comp_threshold_db if chain else -18.0,
            width=_CARD_W - 14, format="%.1f",
            callback=lambda s, v: _set(chain, "comp_threshold_db", v),
        )
        dpg.add_text("Ratio", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_comp_ratio",
            min_value=1.0, max_value=20.0,
            default_value=chain.comp_ratio if chain else 3.0,
            width=_CARD_W - 14, format="%.1f",
            callback=lambda s, v: _set(chain, "comp_ratio", v),
        )


def _limiter_card(state: AppState) -> None:
    chain = state.effects_chain
    with dpg.child_window(width=_CARD_W, height=_CARD_H, border=True):
        dpg.add_checkbox(
            label=" Limiter",
            tag="fx_lim_en",
            default_value=chain.limiter_enabled if chain else True,
            callback=lambda s, v: _set(chain, "limiter_enabled", v),
        )
        dpg.add_spacer(height=4)
        dpg.add_text("Threshold dB", color=_LABEL_C)
        dpg.add_slider_float(
            tag="fx_lim_thresh",
            min_value=-6.0, max_value=0.0,
            default_value=chain.limiter_threshold_db if chain else -1.0,
            width=_CARD_W - 14, format="%.1f",
            callback=lambda s, v: _set(chain, "limiter_threshold_db", v),
        )


# ---------------------------------------------------------------------------
# Preset row
# ---------------------------------------------------------------------------

def _preset_row(state: AppState) -> None:
    with dpg.group(horizontal=True):
        dpg.add_input_text(
            tag="fx_preset_name",
            hint="Preset name…",
            width=160,
        )
        dpg.add_button(
            label="Save",
            width=54,
            callback=lambda: _save_preset(state),
        )
        dpg.add_button(
            label="Load",
            width=54,
            callback=lambda: _load_preset(state),
        )
        dpg.add_button(
            label="Del",
            width=40,
            callback=lambda: _delete_preset(state),
        )
        dpg.add_combo(
            tag="fx_preset_combo",
            items=_refresh_preset_list(),
            width=180,
            callback=lambda s, v: dpg.set_value("fx_preset_name", v),
        )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _set(chain, attr: str, value) -> None:
    """Write a param and mark the chain dirty so the board rebuilds."""
    if chain is None:
        return
    setattr(chain, attr, value)
    chain.mark_dirty()


def _refresh_preset_list() -> list[str]:
    try:
        from engine.effects.chain import EffectsChain
        return EffectsChain.list_presets()
    except Exception:
        return []


def _save_preset(state: AppState) -> None:
    if state.effects_chain is None:
        return
    name = dpg.get_value("fx_preset_name").strip()
    if not name:
        return
    state.effects_chain.save_preset(name)
    dpg.configure_item("fx_preset_combo", items=_refresh_preset_list())


def _load_preset(state: AppState) -> None:
    from engine.effects.chain import EffectsChain
    name = dpg.get_value("fx_preset_name").strip()
    if not name:
        name = dpg.get_value("fx_preset_combo")
    if not name:
        return
    loaded = EffectsChain.load_preset(name)
    if loaded is None:
        return
    state.effects_chain = loaded
    _sync_ui_to_chain(loaded)


def _delete_preset(state: AppState) -> None:
    from engine.effects.chain import EffectsChain
    name = dpg.get_value("fx_preset_name").strip() or dpg.get_value("fx_preset_combo")
    if not name:
        return
    EffectsChain.delete_preset(name)
    dpg.configure_item("fx_preset_combo", items=_refresh_preset_list())


def _sync_ui_to_chain(chain) -> None:
    """Push loaded preset values back into the DPG widgets."""
    pairs = {
        "fx_hp_en":      chain.hp_enabled,
        "fx_hp_cutoff":  chain.hp_cutoff_hz,
        "fx_lp_en":      chain.lp_enabled,
        "fx_lp_cutoff":  chain.lp_cutoff_hz,
        "fx_rev_en":     chain.reverb_enabled,
        "fx_rev_room":   chain.reverb_room_size,
        "fx_rev_wet":    chain.reverb_wet_level,
        "fx_cho_en":     chain.chorus_enabled,
        "fx_cho_rate":   chain.chorus_rate_hz,
        "fx_cho_depth":  chain.chorus_depth,
        "fx_comp_en":    chain.comp_enabled,
        "fx_comp_thresh": chain.comp_threshold_db,
        "fx_comp_ratio": chain.comp_ratio,
        "fx_lim_en":     chain.limiter_enabled,
        "fx_lim_thresh": chain.limiter_threshold_db,
    }
    for tag, val in pairs.items():
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, val)
