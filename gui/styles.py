"""
Centralized stylesheet for the Measurement GUI.

Single place to tweak every colour, font-size, and spacing.
Uses a dark-ish scientific-instrument theme.
"""

# -- Colour palette --------------------------------------------------------
BG_PRIMARY    = "#1e1e2e"   # Main background
BG_PANEL      = "#282840"   # Panel / group-box background
BG_INPUT      = "#33334d"   # Input field background
ACCENT        = "#4fc3f7"   # Accent (buttons, highlights)
ACCENT_HOVER  = "#81d4fa"
ACCENT_PRESS  = "#0288d1"
TEXT_PRIMARY   = "#e0e0e0"  # Main text
TEXT_SECONDARY = "#a0a0b0"  # Labels, secondary text
TEXT_TITLE     = "#ffffff"
BORDER         = "#444466"
DANGER         = "#ef5350"
DANGER_HOVER   = "#e57373"
SUCCESS        = "#66bb6a"

STYLESHEET = f"""
/* ── Global ───────────────────────────────────────────── */
QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}}

/* ── Top Bar ──────────────────────────────────────────── */
#TopBar {{
    background-color: {BG_PANEL};
    border-bottom: 2px solid {BORDER};
    padding: 6px 12px;
}}
#TitleLabel {{
    color: {TEXT_TITLE};
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 1px;
}}

/* ── Group Boxes (panels) ─────────────────────────────── */
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: bold;
    font-size: 13px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT};
}}

/* ── Labels ───────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel[role="unit"] {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

/* ── Line Edits / Spin Boxes ──────────────────────────── */
QLineEdit, QDoubleSpinBox, QSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

/* ── Buttons ──────────────────────────────────────────── */
QPushButton {{
    background-color: {ACCENT};
    color: #000000;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PRESS};
    color: #ffffff;
}}
QPushButton:disabled {{
    background-color: {BORDER};
    color: {TEXT_SECONDARY};
}}
QPushButton#ExitButton {{
    background-color: {DANGER};
    color: #ffffff;
    font-size: 13px;
    padding: 6px 20px;
}}
QPushButton#ExitButton:hover {{
    background-color: {DANGER_HOVER};
}}
QPushButton#RunButton {{
    font-size: 16px;
    padding: 10px 40px;
    border-radius: 6px;
}}

/* ── Radio Buttons / Check Boxes ──────────────────────── */
QRadioButton, QCheckBox {{
    spacing: 6px;
    background: transparent;
}}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {BORDER};
    border-radius: 3px;
    background: {BG_INPUT};
}}
QRadioButton::indicator {{
    border-radius: 10px;
}}
QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Status Bar ───────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_PANEL};
    color: {TEXT_SECONDARY};
    font-size: 12px;
    border-top: 1px solid {BORDER};
}}

/* ── Scroll Area (for graph panel later) ──────────────── */
QScrollArea {{
    border: none;
}}

/* ── ToolTip ──────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
    font-size: 12px;
}}
"""
