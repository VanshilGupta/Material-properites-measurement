"""
Centralized stylesheet for the Measurement GUI.

Professional neutral-dark theme for lab environments.
Uses absolute path for the checkmark SVG so it works in dev and packaged builds.
"""

import pathlib

# ── Asset paths ────────────────────────────────────────────────────────────
_ASSETS    = pathlib.Path(__file__).resolve().parent / "assets"
_CHECK_SVG = (_ASSETS / "check.svg").as_posix()

# ── Colour palette ─────────────────────────────────────────────────────────
BG_PRIMARY     = "#1A1A1A"
BG_PANEL       = "#252525"
BG_INPUT       = "#333333"
ACCENT         = "#5B9BD5"
ACCENT_HOVER   = "#79B8F8"
ACCENT_PRESS   = "#3A7CC0"
TEXT_PRIMARY   = "#E8E8E8"
TEXT_SECONDARY = "#909090"
TEXT_TITLE     = "#FFFFFF"
BORDER         = "#404040"
BORDER_LIGHT   = "#505050"
DANGER         = "#D9534F"
DANGER_HOVER   = "#E06B67"
SUCCESS        = "#4EC94E"

STYLESHEET = f"""
/* ── Global ──────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}}

/* ── Top Bar ─────────────────────────────────────────────────────────── */
#TopBar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
#TitleLabel {{
    color: {TEXT_TITLE};
    font-size: 17px;
    font-weight: bold;
    letter-spacing: 0.5px;
}}

/* ── Section Headers ─────────────────────────────────────────────────── */
#SectionHeader {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
#SectionLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
}}

/* ── Group Boxes ─────────────────────────────────────────────────────── */
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 5px;
    margin-top: 18px;
    padding: 10px 10px 8px 10px;
    font-weight: bold;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {ACCENT};
    font-size: 12px;
    font-weight: bold;
}}

/* ── Labels ──────────────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel#LiveReadout {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 15px;
    font-weight: bold;
    color: {SUCCESS};
    background: transparent;
    min-width: 110px;
}}

/* ── Inputs ──────────────────────────────────────────────────────────── */
QLineEdit, QDoubleSpinBox, QSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    min-height: 24px;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {{
    color: {TEXT_SECONDARY};
    background-color: #2A2A2A;
    border-color: #363636;
}}

/* Spin-box arrow buttons */
QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    border-top-right-radius: 4px;
    background: {BG_INPUT};
}}
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border-left: 1px solid {BORDER};
    border-top: 1px solid {BORDER};
    border-bottom-right-radius: 4px;
    background: {BG_INPUT};
}}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background: {BORDER_LIGHT};
}}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT_SECONDARY};
    width: 0; height: 0;
}}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    width: 0; height: 0;
}}
QDoubleSpinBox::up-arrow:hover, QSpinBox::up-arrow:hover {{
    border-bottom-color: {TEXT_PRIMARY};
}}
QDoubleSpinBox::down-arrow:hover, QSpinBox::down-arrow:hover {{
    border-top-color: {TEXT_PRIMARY};
}}

/* ── Buttons (default) ───────────────────────────────────────────────── */
QPushButton {{
    background-color: {ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover   {{ background-color: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background-color: {ACCENT_PRESS}; }}
QPushButton:disabled {{
    background-color: #383838;
    color: {TEXT_SECONDARY};
}}

QPushButton#ExitButton {{
    background-color: {BG_INPUT};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    font-size: 12px;
    padding: 4px 14px;
}}
QPushButton#ExitButton:hover {{
    background-color: {BORDER};
    color: {TEXT_PRIMARY};
}}

QPushButton#AbortButton {{
    background-color: {DANGER};
    font-size: 14px;
    font-weight: bold;
    padding: 8px 28px;
    border-radius: 5px;
    letter-spacing: 1px;
    max-width: 240px;
}}
QPushButton#AbortButton:hover {{ background-color: {DANGER_HOVER}; }}

QPushButton#RunButton {{
    font-size: 14px;
    padding: 8px 32px;
    border-radius: 5px;
    letter-spacing: 1px;
    max-width: 240px;
}}

/* Small icon-only buttons (collapse / maximize arrows) */
QPushButton#IconButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 0px;
    font-size: 13px;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    font-weight: bold;
}}
QPushButton#IconButton:hover {{
    background-color: {BORDER};
    color: {TEXT_PRIMARY};
}}

/* Toggle pill (Enable Cycle) */
QPushButton#ToggleButton {{
    background-color: {BG_INPUT};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 11px;
    padding: 2px 14px 2px 8px;
    font-size: 12px;
    font-weight: bold;
    min-width: 80px;
    text-align: left;
}}
QPushButton#ToggleButton:hover {{
    border-color: {BORDER_LIGHT};
    color: {TEXT_PRIMARY};
}}
QPushButton#ToggleButton:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #FFFFFF;
    padding: 2px 8px 2px 14px;
    text-align: right;
}}

/* ── Segmented Toggle (Experiment Mode) ──────────────────────────────── */
#SegmentedToggle {{
    background-color: #2A2A2A;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 2px;
}}
QPushButton#SegmentBtn {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px 0;
    color: {TEXT_SECONDARY};
    font-size: 12px;
    font-weight: bold;
    min-height: 22px;
}}
QPushButton#SegmentBtn:hover {{
    color: {TEXT_PRIMARY};
    background: rgba(255, 255, 255, 0.05);
}}
QPushButton#SegmentBtn:checked {{
    background-color: {ACCENT};
    color: #FFFFFF;
}}
QPushButton#SegmentBtn:disabled {{
    color: #555555;
}}

/* ── Radio Buttons ───────────────────────────────────────────────────── */
QRadioButton {{
    spacing: 7px;
    background: transparent;
    color: {TEXT_PRIMARY};
    padding: 2px 0;
}}
QRadioButton:disabled {{ color: {TEXT_SECONDARY}; }}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 2px solid {BORDER_LIGHT};
    border-radius: 8px;
    background: transparent;
}}
QRadioButton::indicator:hover  {{ border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{
    border-color: {ACCENT};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
        fx:0.5, fy:0.5,
        stop:0 {ACCENT}, stop:0.55 {ACCENT},
        stop:0.56 transparent, stop:1 transparent);
}}

/* ── Check Boxes — tick mark via SVG ─────────────────────────────────── */
QCheckBox {{
    spacing: 7px;
    background: transparent;
    color: {TEXT_PRIMARY};
    padding: 2px 0;
}}
QCheckBox:disabled {{ color: {TEXT_SECONDARY}; }}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 2px solid {BORDER_LIGHT};
    border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:hover   {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: url("{_CHECK_SVG}");
}}

/* ── Splitters ───────────────────────────────────────────────────────── */
QSplitter::handle            {{ background-color: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical   {{ height: 2px; }}
QSplitter::handle:hover      {{ background-color: {ACCENT}; }}

/* ── Status Bar ──────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_PANEL};
    color: {TEXT_SECONDARY};
    font-size: 11px;
    border-top: 1px solid {BORDER};
}}

/* ── Log Text Area ───────────────────────────────────────────────────── */
QPlainTextEdit#LogArea {{
    background-color: #111111;
    color: #B0B0B0;
    border: none;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 4px;
}}

/* ── Scroll Bars (thin, unobtrusive) ─────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_PRIMARY};
    width: 7px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {BORDER_LIGHT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_PRIMARY};
    height: 7px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {BORDER_LIGHT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Scroll Area ─────────────────────────────────────────────────────── */
QScrollArea               {{ border: none; background: transparent; }}
QScrollArea > QWidget     {{ background: transparent; }}

/* ── ToolTip ─────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    padding: 4px 6px;
    font-size: 11px;
}}

/* ── Status Card (bottom of left panel) ──────────────────────────────── */
#StatusCard {{
    background-color: {BG_PANEL};
    border-top: 1px solid {BORDER};
}}
#CurrentTempValue {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 22px;
    font-weight: bold;
    color: {SUCCESS};
    background: transparent;
    padding: 6px 0;
}}

/* ── Log Clear Button ────────────────────────────────────────────────── */
QPushButton#LogClearButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 1px 10px;
    font-size: 10px;
    font-weight: bold;
}}
QPushButton#LogClearButton:hover {{
    background-color: {BORDER};
    color: {TEXT_PRIMARY};
}}

/* ── Instrument Status Indicators (status bar) ───────────────────────── */
#InstrumentStatusWidget {{
    background: transparent;
}}
.InstrumentDot {{
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
    border-radius: 4px;
    background: transparent;
}}
.InstrumentLabel {{
    font-size: 11px;
    color: {TEXT_SECONDARY};
    background: transparent;
    padding: 0;
}}
"""
