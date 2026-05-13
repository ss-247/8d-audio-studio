"""
Main application class — sets up Dear PyGui, wires all panels to the engine,
and runs the render loop.
"""

from __future__ import annotations

import threading
from pathlib import Path

import dearpygui.dearpygui as dpg

from ui.state import AppState
from ui.theme import apply_theme
from engine.playback import PlaybackEngine
from engine.spatial.rotation import make_path, CirclePath
import ui.panels.transport as transport_panel
import ui.panels.waveform as waveform_panel
import ui.panels.spatial_viz as spatial_panel
import ui.panels.effects as effects_panel
from engine.effects.chain import EffectsChain


class App:
    def __init__(self) -> None:
        self.state = AppState()
        self.state.effects_chain = EffectsChain()
        self.engine = PlaybackEngine()
        self.engine.set_effects_chain(self.state.effects_chain)
        self._rotation_path = CirclePath(speed_hz=0.15)
        self._processing_thread: threading.Thread | None = None
        self._hrtf = None           # loaded once, reused for both preview and export
        self._hrtf_loading = False
        self._prev_preview = False  # tracks last preview state to detect toggles
        self._prev_path_key = self.state.rotation_path
        self._prev_speed    = self.state.rotation_speed

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        dpg.create_context()
        dpg.bind_theme(apply_theme())

        dpg.create_viewport(title="8D Studio", width=1280, height=800,
                            min_width=900, min_height=600)
        dpg.setup_dearpygui()

        self._build_file_dialogs()
        self._build_main_window()

        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while dpg.is_dearpygui_running():
            self._update()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_file_dialogs(self) -> None:
        # Open audio file dialog
        with dpg.file_dialog(
            directory_selector=False, show=False,
            callback=self._on_file_selected,
            cancel_callback=lambda s, a: None,
            tag="open_file_dialog", width=720, height=480,
        ):
            dpg.add_file_extension(".wav",  color=(100, 220, 100, 255), custom_text="[WAV]")
            dpg.add_file_extension(".mp3",  color=(220, 180, 80,  255), custom_text="[MP3]")
            dpg.add_file_extension(".flac", color=(100, 180, 220, 255), custom_text="[FLAC]")
            dpg.add_file_extension(".ogg",  color=(200, 100, 220, 255), custom_text="[OGG]")
            dpg.add_file_extension(".*")

        # Export directory picker
        with dpg.file_dialog(
            directory_selector=True, show=False,
            callback=self._on_export_dir_selected,
            cancel_callback=lambda s, a: None,
            tag="export_file_dialog", width=720, height=480,
        ):
            pass

    def _build_main_window(self) -> None:
        with dpg.window(
            tag="main_window", no_title_bar=True, no_move=True,
            no_resize=True, no_scrollbar=True, menubar=True,
        ):
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="Open Audio File...", shortcut="Ctrl+O",
                                      callback=lambda: dpg.show_item("open_file_dialog"))
                    dpg.add_separator()
                    dpg.add_menu_item(label="Exit", callback=dpg.stop_dearpygui)

            dpg.add_spacer(height=8)
            transport_panel.setup(self.state, self.engine, parent="main_window")
            dpg.add_spacer(height=8)
            dpg.add_separator()
            dpg.add_spacer(height=10)
            waveform_panel.setup(self.state, self.engine, parent="main_window")
            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_spacer(height=10)
            effects_panel.setup(self.state, parent="main_window")
            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_spacer(height=10)
            spatial_panel.setup(self.state, parent="main_window")

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def _update(self) -> None:
        # Sync from engine
        self.state.playback_position    = self.engine.playback_position
        self.state.current_time_seconds = self.engine.current_time_seconds
        self.state.is_playing           = self.engine.is_playing

        # Rebuild rotation path if settings changed
        self._sync_rotation_path()

        # Live rotation angle — drives the viz dot during playback
        if self.engine.is_playing:
            t = self.engine.current_time_seconds
            az, el = self._rotation_path.get_angle(t)
            self.state.rotation_angle     = az
            self.state.rotation_elevation = el

        self._handle_spatial_preview()
        transport_panel.update(self.state, self.engine)
        waveform_panel.update(self.state)
        effects_panel.update(self.state)
        spatial_panel.update(self.state)

    def _sync_rotation_path(self) -> None:
        key = self.state.rotation_path
        spd = self.state.rotation_speed
        changed = (key != self._prev_path_key or abs(spd - self._prev_speed) > 1e-4)
        if changed:
            self._rotation_path = make_path(key, spd)
            self._prev_path_key = key
            self._prev_speed    = spd
            if self.state.spatial_preview and self._hrtf is not None:
                self.engine.update_rotation_path(self._rotation_path)

    def _handle_spatial_preview(self) -> None:
        preview = self.state.spatial_preview
        if preview == self._prev_preview:
            return
        self._prev_preview = preview

        if preview:
            if self._hrtf is None and not self._hrtf_loading:
                self._load_hrtf_async()
            elif self._hrtf is not None:
                self.engine.enable_spatial(self._hrtf, self._rotation_path)
        else:
            self.engine.disable_spatial()

    def _load_hrtf_async(self) -> None:
        self._hrtf_loading = True
        self.state.status_message = "Loading HRTF..."

        def _load():
            from engine.spatial.hrtf import HRTFDatabase
            sofa = Path(__file__).resolve().parents[1] / "data/hrtf/mit_kemar.sofa"
            try:
                self._hrtf = HRTFDatabase(sofa)
                if self.state.spatial_preview:
                    self.engine.enable_spatial(self._hrtf, self._rotation_path)
                self.state.status_message = "HRTF loaded — Live Preview ready"
            except Exception as exc:
                self.state.status_message = f"HRTF load failed: {exc}"
            finally:
                self._hrtf_loading = False

        threading.Thread(target=_load, daemon=True).start()

    # ------------------------------------------------------------------
    # Callbacks — file open
    # ------------------------------------------------------------------

    def _on_file_selected(self, sender, app_data: dict) -> None:
        path_str = app_data.get("file_path_name", "")
        if not path_str:
            return
        path = Path(path_str)
        if not path.exists():
            self.state.status_message = f"Not found: {path.name}"
            return

        self.state.status_message = f"Loading {path.name}..."
        try:
            audio, sr = self.engine.load_audio(path)
        except Exception as exc:
            self.state.status_message = f"Error: {exc}"
            return

        self.state.audio_data        = audio
        self.state.sample_rate       = sr
        self.state.audio_path        = path
        self.state.playback_position = 0.0
        ch  = audio.shape[1] if audio.ndim > 1 else 1
        dur = len(audio) / sr
        self.state.status_message = f"{path.name}  |  {sr} Hz  |  {ch}ch  |  {dur:.1f}s"
        waveform_panel.draw_waveform(audio, sr)

    # ------------------------------------------------------------------
    # Callbacks — export / processing
    # ------------------------------------------------------------------

    def _on_export_dir_selected(self, sender, app_data: dict) -> None:
        if self.state.audio_data is None:
            self.state.status_message = "No audio loaded — open a file first"
            return
        if self._processing_thread and self._processing_thread.is_alive():
            self.state.status_message = "Already processing — please wait"
            return

        out_dir = Path(app_data.get("file_path_name", ""))
        if not out_dir.is_dir():
            out_dir = out_dir.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        stem   = (self.state.audio_path.stem if self.state.audio_path else "output")
        suffix = "_8d" if self.state.spatial_mode == "8d" else "_stereo"
        out_path = out_dir / f"{stem}{suffix}.wav"

        self._processing_thread = threading.Thread(
            target=self._run_processing,
            args=(out_path,),
            daemon=True,
        )
        self._processing_thread.start()

    def _run_processing(self, out_path: Path) -> None:
        from engine.export import export_wav

        self.state.is_processing       = True
        self.state.processing_progress = 0.0
        self.state.status_message      = "Processing..."

        try:
            audio = self.state.audio_data
            sr    = self.state.sample_rate

            # Apply effects chain before spatial processing
            if self.state.effects_chain is not None:
                audio = self.state.effects_chain.process(audio, sr)

            if self.state.spatial_mode == "8d":
                from engine.spatial.hrtf import HRTFDatabase
                from engine.spatial.binaural import BinauralProcessor

                if self._hrtf is None:
                    sofa = Path(__file__).resolve().parents[1] / "data/hrtf/mit_kemar.sofa"
                    self._hrtf = HRTFDatabase(sofa)
                hrtf = self._hrtf
                path = make_path(self.state.rotation_path, self.state.rotation_speed)

                def on_angle(az, el):
                    self.state.rotation_angle     = az
                    self.state.rotation_elevation = el

                proc   = BinauralProcessor(hrtf, path,
                                           on_progress=lambda p: setattr(self.state, "processing_progress", p),
                                           on_angle=on_angle)
                result = proc.process(audio, sr)
            else:
                from engine.spatial.stereo import StereoWidener
                result = StereoWidener(width=1.5).process(audio, sr)
                self.state.processing_progress = 1.0

            export_wav(result, sr, out_path)
            self.state.status_message = f"Saved: {out_path.name}"
            dpg.set_value("export_status", f"Saved: {out_path.name}")

        except Exception as exc:
            self.state.status_message = f"Processing error: {exc}"
            dpg.set_value("export_status", f"Error: {exc}")
        finally:
            self.state.is_processing       = False
            self.state.processing_progress = 0.0
