"""Dark studio colour theme for Dear PyGui."""

import dearpygui.dearpygui as dpg


def apply_theme() -> int:
    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvAll):
            # Backgrounds
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg,       (18,  18,  22,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg,        (24,  24,  30,  255))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg,        (28,  28,  36,  255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg,        (35,  35,  45,  255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (50,  50,  65,  255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive,  (60,  60,  80,  255))

            # Title bars
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg,        (15,  15,  20,  255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive,  (25,  25,  50,  255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed,(10, 10,  15,  255))

            # Accent / interactive
            dpg.add_theme_color(dpg.mvThemeCol_Button,         (50,  80,  160, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,  (70,  110, 210, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,   (40,  60,  130, 255))
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark,      (100, 160, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab,     (80,  130, 230, 255))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive,(100,160, 255, 255))

            # Headers
            dpg.add_theme_color(dpg.mvThemeCol_Header,         (40,  60,  120, 200))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered,  (55,  80,  160, 220))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive,   (65,  95,  180, 255))

            # Separators / borders
            dpg.add_theme_color(dpg.mvThemeCol_Separator,      (60,  60,  80,  255))
            dpg.add_theme_color(dpg.mvThemeCol_Border,         (45,  45,  60,  255))

            # Text
            dpg.add_theme_color(dpg.mvThemeCol_Text,           (220, 220, 235, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled,   (100, 100, 120, 255))

            # Scrollbars
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,    (18,  18,  22,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,  (60,  60,  90,  255))

            # Tabs
            dpg.add_theme_color(dpg.mvThemeCol_Tab,            (30,  30,  50,  255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered,     (55,  80,  160, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive,      (50,  75,  150, 255))

            # Rounding / spacing
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding,  6)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding,   4)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding,    4)
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding,     4)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding,   12, 10)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding,    8,  4)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing,     8,  6)

    return theme_id
