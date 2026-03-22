# UI Technical Reference  
## Thermoelectric Measurement System — GUI

> **Audience:** Anyone who needs to make small changes to the UI without prior PySide6 knowledge.  
> **Last updated:** Based on the state of the codebase after all Phase 1–4 refinements.

---

## Table of Contents

1. [Quick PySide6 Concepts Primer](#1-quick-pyside6-concepts-primer)
2. [File Map](#2-file-map)
3. [Colour & Style System — `gui/styles.py`](#3-colour--style-system--guistylespy)
4. [Main Window — `gui/main_window.py`](#4-main-window--guimain_windowpy)
5. [Sample Information Panel — `gui/widgets/sample_info.py`](#5-sample-information-panel--guiwidgetssample_infopy)
6. [Method Configuration Panel — `gui/widgets/method_config.py`](#6-method-configuration-panel--guiwidgetsmethod_configpy)
7. [Temperature Profile Panel — `gui/widgets/temperature.py`](#7-temperature-profile-panel--guiwidgetstemperaturepy)
8. [Graph Panel — `gui/widgets/graph_panel.py`](#8-graph-panel--guiwidgetsgraph_panelpy)
9. [Log Panel — `gui/widgets/log_panel.py`](#9-log-panel--guiwidgetslog_panelpy)
10. [How-To Recipes — Common Small Changes](#10-how-to-recipes--common-small-changes)

---

## 1. Quick PySide6 Concepts Primer

### Widgets
A **widget** is any visual element — a button, a text box, a label, the entire window.  
Everything inherits from `QWidget`. You construct a widget in Python, set properties on it, then place it inside a **layout**.

### Layouts
A **layout** is an invisible manager that positions widgets automatically.

| Layout | Direction | Use |
|---|---|---|
| `QHBoxLayout` | Left → Right | Put things side by side |
| `QVBoxLayout` | Top → Bottom | Stack things vertically |
| `QFormLayout` | Two-column label + field | Data-entry forms |
| `QGridLayout` | Arbitrary row/col grid | Tables of widgets |

You do **not** set pixel positions manually. Add widgets to a layout via `layout.addWidget(widget)` and Qt handles the rest.

```python
row = QHBoxLayout()
row.addWidget(label)   # goes left
row.addWidget(input)   # goes right of label
```

**`addStretch()`** inserts an invisible elastic "spring" that absorbs leftover space:

```python
row.addWidget(button)
row.addStretch()   # button stays left, empty space fills the right
```

### Signals & Slots
Qt uses an event system called **signals and slots**.

- A **signal** is a notification a widget can emit (fire).
- A **slot** is a function/method that runs when a signal fires.
- You wire them together with `.connect()`.

```python
# When the user changes the text, call _on_name_changed
self.name_edit.textChanged.connect(self._on_name_changed)

# When button is clicked, call _on_run
self.run_btn.clicked.connect(self._on_run)
```

Custom signals are declared at the class level:

```python
class MyPanel(QGroupBox):
    my_signal = Signal(str, float)   # will carry a str and a float

    def something_happened(self):
        self.my_signal.emit("hello", 3.14)
```

### Object Names & Stylesheets
Qt stylesheets work exactly like CSS but use `#ObjectName` selectors.

```python
button.setObjectName("RunButton")
```

In the stylesheet:
```css
QPushButton#RunButton {
    font-size: 14px;
    padding: 8px 32px;
}
```

All styles live in **one place**: `gui/styles.py`. You almost never need to set a style directly on a widget; find and edit the rule in `styles.py` instead.

### Size Policies
`QSizePolicy` controls how a widget behaves when the window is resized.

| Policy | Meaning |
|---|---|
| `Fixed` | Stays exactly the size you set. Never grows or shrinks. |
| `Minimum` | At least the minimum; can grow. |
| `Expanding` | Grows to fill all available space. |

```python
widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
# Grows horizontally, stays fixed height
```

### Splitters
`QSplitter` places its children side-by-side (or top/bottom) with a draggable handle between them. The user can drag the handle to resize the panel.

```python
splitter = QSplitter(Qt.Horizontal)  # left | right
splitter.addWidget(left_panel)
splitter.addWidget(right_panel)
splitter.setSizes([600, 600])  # starting pixel sizes
```

### QGroupBox
A named container with a visible border and title, used for each "section" in the left panel (e.g., "SAMPLE INFORMATION").

---

## 2. File Map

```
gui/
├── styles.py                  ← ALL colours, fonts, widget styles
├── main_window.py             ← Top-level window, splitters, wiring
├── backend/
│   └── eurotherm_service.py   ← Hardware communication (not UI)
└── widgets/
    ├── __init__.py            ← Re-exports all panels (import convenience)
    ├── sample_info.py         ← Section 1: Sample name/dia/thickness
    ├── method_config.py       ← Section 2: Mode toggle, radios, checkboxes
    ├── temperature.py         ← Section 3: Target temp + cycle settings
    ├── graph_panel.py         ← Reusable graph (used for both Seebeck + σ)
    └── log_panel.py           ← Bottom log strip
```

Each widget file is **self-contained**: it builds its own UI, exposes a clean public API, and communicates upward via signals. `main_window.py` connects them together.

---

## 3. Colour & Style System — `gui/styles.py`

### Colour Constants

These Python variables at the top of `styles.py` drive the entire theme. Change one value here and it propagates everywhere.

| Variable | Hex Value | Used For |
|---|---|---|
| `BG_PRIMARY` | `#1A1A1A` | Main background, graph background |
| `BG_PANEL` | `#252525` | Group boxes, top bar, status card, log header |
| `BG_INPUT` | `#333333` | Text fields, spinboxes, button backgrounds |
| `ACCENT` | `#5B9BD5` | Blue highlight: focused borders, active buttons, graph line |
| `ACCENT_HOVER` | `#79B8F8` | Lighter blue on hover |
| `ACCENT_PRESS` | `#3A7CC0` | Darker blue on press |
| `TEXT_PRIMARY` | `#E8E8E8` | All normal text, graph axis labels/ticks |
| `TEXT_SECONDARY` | `#909090` | Dimmed text, section headers, spine lines |
| `TEXT_TITLE` | `#FFFFFF` | Top bar title |
| `BORDER` | `#404040` | Widget borders, splitter handles |
| `BORDER_LIGHT` | `#505050` | Slightly lighter borders on hover |
| `DANGER` | `#D9534F` | ABORT button background |
| `DANGER_HOVER` | `#E06B67` | ABORT button on hover |
| `SUCCESS` | `#4EC94E` | Current temperature readout (green) |

### The Stylesheet (`STYLESHEET`)
One large multi-line f-string that is applied to the entire application:

```python
app.setStyleSheet(STYLESHEET)   # done in MainWindow.__init__
```

It uses f-string interpolation to embed the colour constants:
```python
STYLESHEET = f"""
QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
}}
"""
```

> **Note the double braces `{{` and `}}`.** In Python f-strings, `{{` is a literal `{` and `}}` is a literal `}`. This is required because CSS itself uses single braces.

### Named Widget Styles
Some widgets get a specific style by their object name:

| Object Name | Widget | Special style |
|---|---|---|
| `TopBar` | `QWidget` | Dark panel, bottom border |
| `TitleLabel` | `QLabel` | White, large, bold |
| `SectionHeader` | `QWidget` | Dark panel, bottom border (graph/log headers) |
| `SectionLabel` | `QLabel` | Gray, uppercase, small, spaced |
| `RunButton` | `QPushButton` | Larger font, 14px, max 240px wide |
| `AbortButton` | `QPushButton` | Red, larger font, 14px, max 240px wide |
| `ExitButton` | `QPushButton` | Gray, small |
| `IconButton` | `QPushButton` | Tiny 22×22 transparent box (▶ ◀ and ⛶) |
| `SegmentedToggle` | `QWidget` container | Dark pill container |
| `SegmentBtn` | `QPushButton` | Inside the toggle; active = blue |
| `ToggleButton` | `QPushButton` | Pill-shaped on/off toggle |
| `LiveReadout` | `QLabel` | Monospaced green, 15px |
| `LogArea` | `QPlainTextEdit` | Near-black bg, monospaced |
| `StatusCard` | `QWidget` | Bottom pinned section |
| `CurrentTempValue` | `QLabel` | Monospaced green, 22px bold |

---

## 4. Main Window — `gui/main_window.py`

### Layout Overview

```
QMainWindow
├── MenuWidget → TopBar (QWidget)          height=50px, always visible
└── centralWidget (QWidget)
    └── outer (QVBoxLayout)
        └── v_splitter (QSplitter, Vertical)
            ├── body_widget (QWidget)
            │   └── body_hl (QHBoxLayout)
            │       ├── collapse_strip (QWidget)  width=28px, always visible
            │       │   └── _collapse_btn (◀ / ▶)
            │       └── h_splitter (QSplitter, Horizontal)
            │           ├── _left_panel (QWidget)     min=220px
            │           │   ├── scroll (QScrollArea, sections 1-3)
            │           │   │   ├── SampleInfoPanel
            │           │   │   ├── MethodConfigPanel
            │           │   │   └── TemperatureProfilePanel
            │           │   └── status_card (QWidget, pinned bottom)
            │           │       ├── CURRENT TEMPERATURE label
            │           │       ├── current_temp_lbl (live readout)
            │           │       ├── run_btn (_RunButton)
            │           │       └── abort_btn
            │           └── right (QWidget)
            │               └── graph_splitter (QSplitter, Vertical)
            │                   ├── graph_seebeck (GraphPanel)
            │                   └── graph_sigma (GraphPanel)
            └── log_panel (LogPanel)
```

### Important Constants

```python
_LEFT_INITIAL_FRAC  = 0.50   # left panel starts at 50% of window width
_LEFT_MAX_FRAC      = 0.70   # restored width can't exceed 70% of window
_LEFT_MIN_THRESHOLD = 200    # px — drag below this → auto-collapse
_COLLAPSE_STRIP_W   = 28     # px — thin always-visible strip with ◀/▶ button
```

### Key Attributes (instance variables)
These attributes on `MainWindow` are accessible from any method:

| Attribute | Type | What it is |
|---|---|---|
| `self.h_splitter` | `QSplitter` | Horizontal left/right split |
| `self.v_splitter` | `QSplitter` | Vertical body/log split |
| `self.graph_splitter` | `QSplitter` | Vertical seebeck/sigma split |
| `self.sample_panel` | `SampleInfoPanel` | Section 1 widget |
| `self.method_panel` | `MethodConfigPanel` | Section 2 widget |
| `self.temp_panel` | `TemperatureProfilePanel` | Section 3 widget |
| `self.log_panel` | `LogPanel` | Bottom log strip |
| `self.graph_seebeck` | `GraphPanel` | S vs T graph |
| `self.graph_sigma` | `GraphPanel` | σ vs T graph |
| `self.run_btn` | `_RunButton` | START RUN button |
| `self.abort_btn` | `QPushButton` | ABORT button |
| `self.current_temp_lbl` | `QLabel` | Live temperature display |
| `self.status_label` | `QLabel` | Status bar text |
| `self.eurotherm` | `EurothermService` | Backend hardware service |
| `self._left_collapsed` | `bool` | Whether left panel is hidden |
| `self._measurement_running` | `bool` | Whether a run is in progress |

### The `_RunButton` Subclass
Qt normally **suppresses tooltip events on disabled widgets**. The custom `_RunButton` subclass overrides `event()` to intercept the tooltip event and show it manually:

```python
class _RunButton(QPushButton):
    def event(self, e: QEvent) -> bool:
        if e.type() == QEvent.Type.ToolTip and not self.isEnabled():
            QToolTip.showText(e.globalPos(), self.toolTip(), self)
            return True
        return super().event(e)
```

This is why hovering over a gray (disabled) START RUN button still shows a tooltip explaining what is missing.

### How Startup Size Works — `showEvent`

```python
def showEvent(self, event):
    super().showEvent(event)
    if not self._initial_split_done:
        self._initial_split_done = True
        avail = self.width() - _COLLAPSE_STRIP_W
        left  = int(avail * _LEFT_INITIAL_FRAC)   # 50% of real window width
        right = avail - left
        self.h_splitter.setSizes([left, right])
        self._saved_left_width = left
```

`showEvent` fires the very first time the window is shown on screen, at which point `self.width()` returns the real pixel width (1280). This sets the splitter to exactly 50/50. If you set sizes earlier in `__init__`, Qt doesn't have geometry yet and ignores them.

### RUN Button Validation — `_update_run_btn_state`

This method is called every time a relevant field changes. It checks 5 conditions:

```python
name_ok = bool(self.sample_panel.get_sample_name())   # not empty
dia_ok  = self.sample_panel.get_diameter() > 0.0      # has a valid number
thk_ok  = self.sample_panel.get_thickness() > 0.0     # has a valid number
meas_ok = (seebeck checked OR conductivity checked)    # ≥1 measurement
cycle_ok = (not cycle mode) OR (a radio is checked)   # direction if cycling
```

Only when ALL 5 are True does `run_btn.setEnabled(True)`. The tooltip lists missing items (with bullet points) when False, and says "Start the measurement sequence" when True.

### Lock-on-Run — `_set_running`

```python
def _set_running(self, running: bool):
    self._measurement_running = running
    self.run_btn.setVisible(not running)    # hide START, show ABORT — or vice versa
    self.abort_btn.setVisible(running)
    self.sample_panel.setEnabled(not running)
    self.method_panel.setEnabled(not running)
    self.temp_panel.setEnabled(not running)
```

`setEnabled(False)` on a panel recursively grays out and disables every widget inside it. The graphs and splitters stay interactive.

### Sidebar Collapse/Expand

- **`_collapse_left()`** — saves current left width, hides `_left_panel`, flips arrow to ▶.
- **`_expand_left()`** — shows panel again, restores width (capped at 70%), flips arrow to ◀.
- **`_on_h_splitter_moved()`** — auto-collapses if the user drags the left panel below 200 px.
- **`_toggle_graph_maximize(index)`** — expands one graph panel to full height (gives the other 0 px), or restores 50/50.

### Backend Wiring — `_connect_backend`

All signal→slot connections are established here, including:
- `eurotherm.temperature_read` → `_update_current_temp` (live readout)
- `temp_panel.set_temp_requested` → `_on_set_furnace` (sends target to hardware)
- `method_panel.mode_changed` → `temp_panel.set_cycle_enabled` (enable/disable cycle fields)
- `method_panel.mode_changed` → `_update_run_btn_state`
- `sample_panel.sample_changed` → `_update_run_btn_state`
- `method_panel.settings_changed` → `_update_run_btn_state`

---

## 5. Sample Information Panel — `gui/widgets/sample_info.py`

### What It Looks Like
```
┌─ SAMPLE INFORMATION ─────────────────────────────┐
│  Name:      [_________________________]           │
│  Diameter:  [____]mm  Thickness: [____]mm         │
└───────────────────────────────────────────────────┘
```

### Widget Inventory

| Attribute | Type | Notes |
|---|---|---|
| `self.name_edit` | `QLineEdit` | Free text, `maxWidth=460`, `Expanding` policy |
| `self.diameter_edit` | `QLineEdit` | Numeric only (validator), `fixedWidth=110` |
| `self.thickness_edit` | `QLineEdit` | Numeric only (validator), `fixedWidth=110` |

### Signal

```python
sample_changed = Signal(str, float, float)
# Emitted on any keypress in any field.
# Args: (sample_name, diameter, thickness)
```

### Input Validation
`QDoubleValidator` prevents non-numeric input from being entered:

```python
self.diameter_edit.setValidator(QDoubleValidator(0.001, 100.0, 2))
#                                               min    max   decimals
```

If the field is empty or has invalid text, `get_diameter()` / `get_thickness()` return `0.0`.

### Layout Detail
The diameter and thickness fields share one `QHBoxLayout` row:

```
[diameter_edit][mm]  14px gap  [Thickness:][thickness_edit][mm]  <stretch>
```

The trailing `addStretch()` is critical — without it, the "mm" label of thickness would drift right when the panel is wide.

---

## 6. Method Configuration Panel — `gui/widgets/method_config.py`

### What It Looks Like
```
┌─ METHOD CONFIGURATION ─────────────────────────────────┐
│  Experiment Mode:                                       │
│  [ Current Temperature  |  Temperature Cycle ]         │
│                                                         │
│  Cycle Mode:                                            │
│  ○ Heating Only      ○ Heating + Cooling                │
│                                                         │
│  Measure:                                               │
│  ☐ Seebeck (S)      ☐ Electrical Conductivity (σ)      │
└─────────────────────────────────────────────────────────┘
```

### Widget Inventory

| Attribute | Type | Notes |
|---|---|---|
| `self.btn_current_t` | `QPushButton` | Checkable; left segment of the mode toggle |
| `self.btn_temp_cycle` | `QPushButton` | Checkable; right segment |
| `self._mode_group` | `QButtonGroup` | Exclusive — only one of the two can be active |
| `self.radio_heat_only` | `QRadioButton` | Disabled when in Current Temperature mode |
| `self.radio_heat_cool` | `QRadioButton` | Disabled when in Current Temperature mode |
| `self._cycle_group` | `QButtonGroup` | **Non-exclusive** (allows unchecking all) |
| `self.chk_seebeck` | `QCheckBox` | Measurement selection |
| `self.chk_conductivity` | `QCheckBox` | Measurement selection |

### Signals

```python
mode_changed     = Signal(bool)   # True = Temperature Cycle mode
settings_changed = Signal()       # emitted on any change (for RUN validation)
```

### Segmented Toggle (Experiment Mode)
The two segment buttons live inside a `QWidget` with `objectName="SegmentedToggle"`, which gives it the rounded pill appearance via the stylesheet. They are in an **exclusive** `QButtonGroup` so only one can be checked at a time.

When the mode changes:
- **→ Temperature Cycle:** `radio_heat_only` is auto-selected, cycle radios are enabled.
- **→ Current Temperature:** all radios are unchecked and disabled.

### Why Radios Use a Non-Exclusive Group
If the group were exclusive, Qt would prevent all-unchecked state. But we need to uncheck both radios when switching back to Current Temperature mode. So `_cycle_group.setExclusive(False)` and mutual exclusion is enforced manually in `_on_heat_only_toggled` / `_on_heat_cool_toggled`.

### Grid Layout for Alignment
The radios and checkboxes sit in a `QGridLayout` with three columns:
- **Col 0 & 1:** shrink-to-fit content
- **Col 2:** `stretch=1` — absorbs all extra width on the right

This keeps "Heating Only" and "Heating + Cooling" left-aligned regardless of panel width. The container has `setMaximumWidth(460)`.

### Public API

```python
panel.is_cycle_mode()   # → bool
panel.is_heating_only() # → bool
panel.get_settings()    # → dict with keys: cycle_mode, heating_only,
                        #                   measure_seebeck, measure_conductivity
```

---

## 7. Temperature Profile Panel — `gui/widgets/temperature.py`

### What It Looks Like
```
┌─ TEMPERATURE PROFILE ──────────────────────────────────┐
│  Target temperature:                                    │
│  [350.0 °C]  [SET]                                      │
│                                                         │
│  Cycle Settings:                                        │
│  Start: [  50.0 °C]   Stop:  [ 200.0 °C]               │
│  Step:  [  25.0 °C]   Rate:  [  10.0 °C/min]           │
└─────────────────────────────────────────────────────────┘
```

### Widget Inventory

| Attribute | Type | Range | Default |
|---|---|---|---|
| `self.target_spin` | `QDoubleSpinBox` | 25–1500 °C | 350 °C, `fixedWidth=130` |
| `self.set_btn` | `QPushButton` | — | "SET", `fixedWidth=64` |
| `self.start_spin` | `QDoubleSpinBox` | 25–1500 °C | 50 °C |
| `self.stop_spin` | `QDoubleSpinBox` | 25–1500 °C | 200 °C |
| `self.step_spin` | `QDoubleSpinBox` | 1–200 °C | 25 °C |
| `self.rate_spin` | `QDoubleSpinBox` | 0.1–50 °C/min | 10 °C/min |

### The `_spin()` Helper
A local function inside `_build_ui` that constructs a label+spinbox pair with consistent sizing:

```python
def _spin(label_text, lo, hi, default, suffix, tooltip):
    lbl = QLabel(label_text)
    lbl.setFixedWidth(46)                      # all labels same width
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(default)
    sp.setSuffix(suffix)
    sp.setDecimals(1)
    sp.setMinimumWidth(88)                     # smallest comfortable width
    sp.setMaximumWidth(155)                    # stops growing here
    sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    sp.setToolTip(tooltip)
    return lbl, sp
```

### Layout Detail
Cycle settings use **two separate `QHBoxLayout` rows**, not a grid:

```
row0:  [Start: 46px][start_spin 88-155px]  10px gap  [Stop: 46px][stop_spin]  <stretch>
row1:  [Step:  46px][step_spin  88-155px]  10px gap  [Rate: 46px][rate_spin]  <stretch>
```

The `addStretch()` at the end of each row absorbs extra panel width after the spinboxes reach their maximum (155 px).

"Start:" and "Step:" labels use `AlignLeft` (not `AlignRight`) so they align visually with the "Cycle Settings:" header above them.

### Signal

```python
set_temp_requested = Signal(float)
# Emitted when SET button is clicked, carrying the spinbox value.
```

### Cycle Enable/Disable

```python
panel.set_cycle_enabled(True)   # called by main_window when mode_changed
panel.set_cycle_enabled(False)  # grays out all 4 cycle spinboxes
```

The spinboxes are always **visible**; they just become un-editable (grayed) when not in cycle mode.

### Public API

```python
panel.get_settings()  # → dict with keys: target_temp, start_temp, stop_temp, step, rate
```

---

## 8. Graph Panel — `gui/widgets/graph_panel.py`

### What It Looks Like
```
┌─ S vs T  (Seebeck Coefficient)  ─────────────── [⛶] ─┐
│                                                        │
│   pyqtgraph PlotWidget (dark background, blue line)   │
│                                                        │
└────────────────────────────────────────────────────────┘
```

Two instances of this widget are created in `main_window.py`:

```python
self.graph_seebeck = GraphPanel(
    title="S vs T   (Seebeck Coefficient)",
    x_label="Temperature", y_label="S",
    x_unit="°C", y_unit="µV/K",
)
self.graph_sigma = GraphPanel(
    title="σ vs T   (Electrical Conductivity)",
    x_label="Temperature", y_label="σ",
    x_unit="°C", y_unit="S/cm",
)
```

### Signal

```python
maximize_requested = Signal()
# Emitted when ⛶ is clicked; handled in main_window._toggle_graph_maximize
```

### Plot Configuration (inside `_build_plot`)

| Setting | Value |
|---|---|
| Background | `BG_PRIMARY` = `#1A1A1A` |
| Axis label color | `TEXT_PRIMARY` = `#E8E8E8` |
| Axis tick color | `TEXT_PRIMARY` = `#E8E8E8` |
| Bottom/left spine pen | `TEXT_SECONDARY` = `#909090` |
| Top/right spine pen | `BORDER` = `#404040` (barely visible) |
| Grid | `alpha=0.15` (subtle) |
| Data curve | color=`ACCENT` (#5B9BD5), width=2, circle markers, white outline |

### Public API

```python
graph.append_point(x, y)   # Add one data point; redraws automatically
graph.set_data(x_list, y_list)   # Replace all data at once
graph.clear_data()         # Clear the graph
```

`append_point` works by reading the existing numpy arrays with `.getData()`, appending to them, and calling `.setData()`. This is how live measurement data would be plotted point by point. 

---

## 9. Log Panel — `gui/widgets/log_panel.py`

### What It Looks Like
```
┌─ LOG ────────────────────────────────────────────────┐
│ [10:32:01]  Setting furnace → 350.0 °C               │
│ [10:32:05]  Eurotherm connected                      │
│ [10:32:10]  Starting measurement — BiTe-001          │
└──────────────────────────────────────────────────────┘
```

### Key Properties
- Read-only (`setReadOnly(True)`)
- Max 2000 lines (`setMaximumBlockCount(2000)`) — oldest lines auto-delete
- Monospaced font, dark background (`#111111`), applied via `objectName="LogArea"`

### Public API

```python
log_panel.append("My message")  # Prepends [HH:MM:SS] timestamp automatically
log_panel.clear()               # Clears all text
```

All calls to `log_panel.append(...)` in `main_window.py` go through this method.

---

## 10. How-To Recipes — Common Small Changes

### 10.1 — Change a Colour

Open `gui/styles.py`, find the constant at the top, and change its hex value.

```python
# Before
ACCENT = "#5B9BD5"   # blue

# After
ACCENT = "#E89A3C"   # orange
```

That's all. The change propagates everywhere (all borders, active buttons, graph line, etc.).

---

### 10.2 — Change a Widget's Font Size or Padding

Find the relevant rule in the `STYLESHEET` string in `gui/styles.py`.

**Example:** Make the RUN button use 16px font instead of 14px:

```python
# In STYLESHEET:
QPushButton#RunButton {{
    font-size: 16px;   # change from 14px
    padding: 8px 32px;
    ...
}}
```

---

### 10.3 — Change a Label's Text

Find the `QLabel(...)` call in the relevant widget file and change the string argument.

**Example:** Change "SAMPLE INFORMATION" to "SAMPLE DETAILS":

```python
# In gui/widgets/sample_info.py, line ~22:
super().__init__("SAMPLE DETAILS", parent)   # was "SAMPLE INFORMATION"
```

---

### 10.4 — Change a Spinbox's Default Value or Range

Find the spinbox in the widget, and change `setRange(min, max)` and/or `setValue(default)`.

**Example:** Change the default target temperature from 350 °C to 500 °C:

```python
# In gui/widgets/temperature.py
self.target_spin.setRange(25.0, 1500.0)
self.target_spin.setValue(500.0)   # was 350.0
```

---

### 10.5 — Change an Input's Fixed Width

Find the `setFixedWidth(...)` call on the widget.

**Example:** Make the sample name field narrower:

```python
# In gui/widgets/sample_info.py
self.name_edit.setMaximumWidth(300)   # was 460
```

(Use `setMaximumWidth` for a soft cap that still shrinks, `setFixedWidth` for exact size.)

---

### 10.6 — Add a New Field to the Sample Information Section

Open `gui/widgets/sample_info.py`. Add a new `QLineEdit` and add a row to the `form` layout:

```python
# In _build_ui, after thickness:
self.material_edit = QLineEdit()
self.material_edit.setPlaceholderText("e.g. Bismuth Telluride")
self.material_edit.setMaximumWidth(460)
form.addRow("Material:", self.material_edit)
```

Then connect it to `_emit_change` so the run button re-validates:

```python
# In _connect_signals:
self.material_edit.textChanged.connect(self._emit_change)
```

And expose it via a getter:

```python
def get_material(self) -> str:
    return self.material_edit.text().strip()
```

---

### 10.7 — Add a New Measurement Checkbox

Open `gui/widgets/method_config.py`. Add a `QCheckBox` below the existing two:

```python
# After chk_conductivity (in _build_ui):
self.chk_hall = QCheckBox("Hall Coefficient (R_H)")
self.chk_hall.setCursor(Qt.PointingHandCursor)
self.chk_hall.stateChanged.connect(self.settings_changed)
align_grid.addWidget(self.chk_hall, 4, 0)   # row 4, col 0
```

Then add it to `get_settings()`:

```python
def get_settings(self) -> dict:
    return {
        ...
        "measure_hall": self.chk_hall.isChecked(),
    }
```

---

### 10.8 — Change a Tooltip

Find `.setToolTip(...)` on the relevant widget:

```python
# Example: change abort button tooltip
self.abort_btn.setToolTip("Immediately halt all measurement activity")
```

For the RUN button specifically, the tooltip is set **dynamically** in `_update_run_btn_state()` in `main_window.py`. Find it there:

```python
if can_run:
    self.run_btn.setToolTip("Start the measurement sequence")   # ← change this
```

---

### 10.9 — Add a Log Message from Any Handler

Call `self.log_panel.append("Your message")` from any method in `main_window.py`. The timestamp is added automatically:

```python
def _on_something(self):
    self.log_panel.append("Something happened")
    self.status_label.setText("Something happened")   # shown in bottom status bar
```

---

### 10.10 — Add a Live Graph Data Point

Get a reference to the correct graph and call `append_point`:

```python
# From anywhere in main_window.py:
self.graph_seebeck.append_point(x=temp_celsius, y=seebeck_uV_per_K)
self.graph_sigma.append_point(x=temp_celsius, y=conductivity_S_per_cm)
```

To replace ALL the data at once (e.g., loading from file):

```python
self.graph_seebeck.set_data(temperature_list, seebeck_list)
```

To wipe the graph clean before a new run:

```python
self.graph_seebeck.clear_data()
self.graph_sigma.clear_data()
```

---

### 10.11 — Change the Window's Default Size

In `gui/main_window.py`, `__init__`:

```python
self.resize(1280, 800)   # change to desired (width, height)
```

The window will still be resizable by the user. The minimum size is:

```python
self.setMinimumSize(900, 600)   # cannot shrink below this
```

---

### 10.12 — Change the Left Panel Startup Split Ratio

In `gui/main_window.py`:

```python
_LEFT_INITIAL_FRAC = 0.50   # 0.50 = 50% left, 50% right
                             # change to e.g. 0.40 for narrower left panel
```

---

### 10.13 — Change the Splitter Auto-Collapse Threshold

```python
_LEFT_MIN_THRESHOLD = 200   # px — drag the left panel below this width to auto-collapse
                             # increase to make collapse happen sooner
```

---

### 10.14 — Change Graph Axis Labels or Units

In `main_window.py`, change the constructor arguments:

```python
self.graph_seebeck = GraphPanel(
    title="Seebeck Coefficient vs Temperature",   # header text
    x_label="T",        # axis label (unit appended in parentheses)
    y_label="S",
    x_unit="K",         # was "°C" — appears as "T (K)"
    y_unit="µV/K",
)
```

---

### 10.15 — Add a New Validation Condition to the RUN Button

Open `_update_run_btn_state()` in `gui/main_window.py`. Add another boolean check:

```python
# Example: require material name is also filled
material_ok = bool(self.sample_panel.get_material())

can_run = name_ok and dia_ok and thk_ok and meas_ok and cycle_ok and material_ok

# And add a bullet reason:
if not material_ok:
    reasons.append("• Enter a material name")
```

---

*End of UI Technical Reference*
