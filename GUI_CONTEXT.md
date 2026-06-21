# GUI Implementation Context

> **Purpose**: Complete reference for any AI assistant continuing work on
> the GUI.  Feed this file at the start of a new chat session so the
> assistant knows exactly what exists, what works, and what remains.
>
> **Last updated**: 2026-05-20 — Codebase-wide cleanup pass:
> fixed latent `pyvisa.VisaIOError` NameError in `measure_sigma.py`,
> removed blocking 5 s sleep in `SeebeckPlotter.save_plot`, cleaned
> unused imports and stale aliases, polished docstrings.  No GUI-layer
> behaviour changes.
>
> **Previous (2026-03-03)**: Bug-fix and feature session:
> fixed sigma median line (uses `sigma_completed` signal with corrected σ),
> fixed summary data alignment (tuple-based storage), wired dead plot-saving
> methods (`_save_sigma_iteration_plot`, `_save_seebeck_fit_plot`),
> added graph Download/Reset/Collapse buttons, disabled pyqtgraph right-click
> menu, added DATA PATH section to confirm dialog, added graph collapse/expand.

---

## 1. Project Overview

**Application**: Thermoelectric Material Properties Measurement System  
**Users**: Research labs — BARC, IISc, etc.  
**GUI framework**: PySide6 (Qt for Python)  
**Packaging target**: standalone `.exe` via PyInstaller  
**Repository branch**: `gui_development`

### Key instructions (`.github/instructions/1st.instructions.md`)
- GOD tier Python + PySide6  
- Best practices, simple, elegant, maintainable  
- Existing functionality must never break  
- Will be packaged into standalone `.exe`

---

## 2. Architecture at a Glance

```
gui/
├── __init__.py             # 2 lines — package docstring
├── app.py                  # Entry point — QApplication, sizing, icon
├── styles.py               # Centralized dark theme (~440 lines)
├── main_window.py          # Top-level QMainWindow — all wiring (~1240 lines)
├── assets/
│   ├── check.svg           # Tick mark for QCheckBox
│   └── logo.png            # App icon (also in top bar)
├── backend/
│   ├── __init__.py          # re-exports EurothermService, MeasurementService
│   ├── eurotherm_service.py # Thread-safe Eurotherm wrapper (251 lines)
│   └── measurement_service.py # Thread-safe sigma/seebeck execution (~560 lines)
└── widgets/
    ├── __init__.py          # re-exports all 5 panels
    ├── sample_info.py       # Sample name, diameter, thickness
    ├── method_config.py     # Experiment mode, direction, measurements
    ├── temperature.py       # Target temp + ramp rate + SET, cycle settings
    ├── graph_panel.py       # pyqtgraph PlotWidget wrapper
    └── log_panel.py         # Timestamped log area + Clear button
```

### Threading model

```
GUI thread                          Worker thread (QThread)
───────────                         ──────────────────────
EurothermService  ──private signals──►  _EurothermWorker
   (public API,                          (serial I/O,
    re-emits                              owns EurothermController)
    worker signals)   ◄──signals──

MeasurementService ──_request_run──►  _MeasurementWorker
   (public API,                          (sigma/seebeck execution,
    re-emits                              instrument I/O, file saving)
    worker signals)    ◄──signals──
```

Both services follow the same pattern: the public API lives on the GUI
thread and uses private signals to invoke slots on the worker.  Worker
signals are re-emitted by the service so `MainWindow` only ever connects
to the service.

All serial I/O is isolated on the background thread.  The GUI never
touches the serial port.  Cross-thread calls use Qt queued signal→slot
connections.

### Polling pattern (temperature reads)

Single-shot chain — **no repeating QTimer**.  After each
`read_temperature()` completes (success or failure), a
`QTimer.singleShot(1000, read_temperature)` reschedules the next read
in the `finally` block.  This prevents overlapping reads when the
serial bus is slow (MODBUS at 9600 baud, 2 s timeout).

---

## 3. File-by-File Reference

### `gui/app.py`  (52 lines) — COMPLETE

Entry point.  Creates `QApplication`, sets icon, sizes window to half
the primary screen, centres it, calls `sys.exit(app.exec())`.

Also adds the project root to `sys.path` so sub-modules can import
`constants`, `eurotherm_control`, etc.

**PyInstaller note**: this is the target file for bundling.

---

### `gui/styles.py`  (~440 lines) — COMPLETE

Centralised dark-theme stylesheet applied via `app.setStyleSheet()`.

#### Colour constants (importable)

| Constant        | Value     | Usage                             |
| --------------- | --------- | --------------------------------- |
| `BG_PRIMARY`    | `#1A1A1A` | Main background                   |
| `BG_PANEL`      | `#252525` | Group boxes, headers, status card |
| `BG_INPUT`      | `#333333` | Text inputs, spin boxes           |
| `ACCENT`        | `#5B9BD5` | Buttons, highlights, focus rings  |
| `ACCENT_HOVER`  | `#79B8F8` | Button hover                      |
| `ACCENT_PRESS`  | `#3A7CC0` | Button press                      |
| `TEXT_PRIMARY`   | `#E8E8E8` | Default text                      |
| `TEXT_SECONDARY` | `#909090` | Dimmed labels                     |
| `TEXT_TITLE`     | `#FFFFFF` | Title bar text                    |
| `BORDER`         | `#404040` | Default borders                   |
| `BORDER_LIGHT`   | `#505050` | Hover borders                     |
| `DANGER`         | `#D9534F` | Abort button, errors              |
| `DANGER_HOVER`   | `#E06B67` | Abort hover                       |
| `SUCCESS`        | `#4EC94E` | Current temp readout              |

#### Named widget styles in the stylesheet

TopBar, TitleLabel, SectionHeader, SectionLabel, QGroupBox,
QLabel#LiveReadout, QLineEdit / QDoubleSpinBox / QSpinBox (normal,
focus, disabled), QPushButton (default + ExitButton, AbortButton,
RunButton, IconButton, ToggleButton), SegmentedToggle, SegmentBtn,
QRadioButton, QCheckBox (with SVG check mark), QSplitter::handle,
QStatusBar, QPlainTextEdit#LogArea, QScrollBar (vertical + horizontal),
QScrollArea, QToolTip, StatusCard, CurrentTempValue,
QPushButton#LogClearButton, .InstrumentDot, .InstrumentLabel.

**Current `.InstrumentDot` size**: **12 × 12 px**, border-radius 6 px
(was 8 × 8 px).  `.InstrumentLabel` is 11 px, `TEXT_SECONDARY`.

---

### `gui/main_window.py`  (~1240 lines) — CORE FILE

Top-level `QMainWindow`.  Owns all panels, the `EurothermService`, and
all signal wiring.

#### Layout

```
+------------------------------------------------------------+
| [Logo]         Thermoelectric Measurement System    [Exit]  |  TopBar (50 px)
+------------------------------------------------------------+
| ◀|  Config panel (scrollable)  |  QStackedWidget            |  h_splitter
|   |  1. SAMPLE INFORMATION     |   Page 0: Placeholder      |
|   |  2. METHOD CONFIGURATION   |   Page 1: σ iteration graph |
|   |  3. TEMPERATURE PROFILE    |   Page 2: Seebeck view     |
|   |                            |     T₁/T₂ vs Time          |
|   |  4. STATUS CARD (pinned)   |     V₁/V₂ vs Time          |
|   |     Current Temp           |     V₁ vs V₂ fit (added    |
|   |     [▶ START RUN]          |       at Seebeck end)       |
+------------------------------------------------------------+
|  LOG  (resizable via v_splitter)                            |
+------------------------------------------------------------+
|  Status bar                                                 |
+------------------------------------------------------------+
```

- `h_splitter` (Horizontal): left config panel | right `graph_stack`
- `v_splitter` (Vertical): body | log panel
- `graph_stack` (QStackedWidget): placeholder | sigma view | seebeck view
- `seebeck_graph_splitter` (Vertical inside seebeck view): T graph | V graph | fit graph
- Collapse strip (28 px): ◀/▶ arrow, auto-collapse below 200 px

#### Key attributes

| Attribute                  | Type                     | Purpose                                     |
| -------------------------- | ------------------------ | ------------------------------------------- |
| `eurotherm`                | `EurothermService`       | Backend furnace control                     |
| `measurement_svc`          | `MeasurementService`     | Backend sigma/seebeck measurement runner    |
| `_temp_read_count`         | `int`                    | Throttle heartbeat log (every 30 reads)     |
| `_instrument_states`       | `dict[str, str]`         | Tracks Eurotherm/PS/DAQ connection state    |
| `_inst_dots`               | `dict[str, QLabel]`      | Coloured dots in status bar                 |
| `_inst_labels`             | `dict[str, QLabel]`      | Instrument name labels in status bar        |
| `sample_panel`             | `SampleInfoPanel`        | Sample name, diameter, thickness            |
| `method_panel`             | `MethodConfigPanel`      | Mode toggle, direction, measurements        |
| `temp_panel`               | `TemperatureProfilePanel`| Target temp, rate, SET, cycle settings      |
| `log_panel`                | `LogPanel`               | Timestamped log display                     |
| `graph_stack`              | `QStackedWidget`         | 3-page right panel (placeholder/σ/seebeck)  |
| `_placeholder_label`       | `QLabel`                 | Centred hint on page 0                      |
| `graph_sigma_iter`         | `GraphPanel`             | σ per Iteration (single curve, page 1)      |
| `graph_seebeck_t`          | `GraphPanel`             | T₁/T₂ vs Time (multi-curve, page 2)        |
| `graph_seebeck_v`          | `GraphPanel`             | V₁/V₂ vs Time (multi-curve, page 2)        |
| `graph_fit`                | `GraphPanel`             | V₁ vs V₂ Seebeck fit (Data+Fit, page 2)    |
| `_fit_graph_added`         | `bool`                   | Whether fit graph is in splitter            |
| `seebeck_graph_splitter`   | `QSplitter`              | Vertical splitter inside seebeck view       |
| `current_temp_lbl`         | `QLabel`                 | Live temperature readout (green, mono)      |
| `status_label`             | `QLabel`                 | Status bar message                          |
| `run_btn`                  | `_RunButton`             | START RUN (shows tooltip even disabled)     |
| `abort_btn`                | `QPushButton`            | ABORT (visible only during measurement)     |
| `h_splitter`               | `QSplitter`              | Left/right split                            |
| `v_splitter`               | `QSplitter`              | Body/log split                              |
| `_left_collapsed`          | `bool`                   | Collapse state tracking                     |
| `_measurement_running`     | `bool`                   | Run state tracking                          |
| `_summary_sigma`           | `list[tuple[float,float]]`| Cycle mode: (temp, σ) pairs                |
| `_summary_seebeck`         | `list[tuple[float,float]]`| Cycle mode: (temp, S) pairs                |

#### Inner classes

**`_RunButton`** — Subclasses `QPushButton`, overrides `event()` to
forward `QEvent.ToolTip` when disabled so the user always sees why the
button is greyed out.

**`_MeasurementConfirmDialog`** — Modal confirmation dialog shown before
starting a run.  Displays sample name, diameter, thickness, selected
measurements, **current temperature** (or cycle temperature points),
mode details, and **DATA PATH** section showing output directory.
Accepts optional `current_temp` and `output_dir` parameters.
"Cancel" and "Start Run" buttons both have `Qt.PointingHandCursor`.

**`_MeasurementSummaryDialog`** — Modal summary dialog shown when a
measurement completes.  Shows ✔ (green) or ✖ (red) icon, the full
summary string, and **metadata details** (temperature, σ time, Seebeck
time, total time, data path).  Accepts optional `metadata` dict.
"OK" button with `Qt.PointingHandCursor`.

#### Signal wiring (`_connect_backend`)

```
eurotherm.temperature_read           → _update_current_temp
eurotherm.temperature_read_failed    → _on_temp_read_failed
temp_panel.set_temp_requested        → _on_set_furnace
eurotherm.error_occurred             → _show_error
eurotherm.connection_changed         → _on_connection_state
eurotherm.set_point_reached          → _on_setpoint_sent
method_panel.mode_changed            → temp_panel.set_cycle_enabled
method_panel.mode_changed            → _update_run_btn_state
sample_panel.sample_changed          → _update_run_btn_state
method_panel.settings_changed        → _update_run_btn_state
measurement_svc.log_message          → log_panel.append
measurement_svc.status_message       → status_label.setText  (via lambda)
measurement_svc.instrument_status    → _on_instrument_status
measurement_svc.measurement_finished → _on_measurement_finished
measurement_svc.seebeck_data_point   → _on_seebeck_data_point
measurement_svc.sigma_data_point     → _on_sigma_data_point
measurement_svc.sigma_completed      → _on_sigma_completed
measurement_svc.seebeck_fit_ready    → _on_seebeck_fit_ready
measurement_svc.phase_changed        → _on_phase_changed
method_panel.settings_changed        → _update_graph_placeholder
```

#### Slot behaviour

| Slot                        | Behaviour                                                                    |
| --------------------------- | ---------------------------------------------------------------------------- |
| `_update_current_temp`      | Updates label text; logs heartbeat every 30 reads (≈30 s)                   |
| `_on_temp_read_failed`      | Logs warning; updates status bar                                             |
| `_on_set_furnace`           | Sends ramp rate **then** temperature to service; logs + status               |
| `_on_setpoint_sent`         | Confirms set-point in log + status bar                                       |
| `_on_connection_state`      | Logs "connected" / "disconnected"; updates status bar + instrument dot       |
| `_show_error`               | Logs "ERROR:" + message; updates status bar                                  |
| `_update_run_btn_state`     | 5 conditions: name, diameter, thickness, measurement, cycle dir              |
| `_on_run`                   | Shows `_MeasurementConfirmDialog` (with `current_temp`); handles testing mode seebeck time; on accept calls `measurement_svc.start()` |
| `_on_abort`                 | Confirmation dialog, then `measurement_svc.request_abort()`                  |
| `_on_measurement_finished`  | `(success, summary, metadata)` — `_set_running(False)`, logs ✔/✖, shows `_MeasurementSummaryDialog` with metadata |
| `_on_instrument_status`     | Updates `_instrument_states`, calls `_refresh_instrument_dot()`              |
| `_refresh_instrument_dot`   | Sets dot colour: grey (disconnected), green (idle), blue (active)            |
| `_set_running`              | Toggles RUN/ABORT, locks/unlocks panels, clears all 4 graphs, removes fit graph from splitter if added |
| `_on_seebeck_data_point`    | Converts time→minutes, V→µV; feeds `graph_seebeck_t` and `graph_seebeck_v`  |
| `_on_sigma_data_point`      | Appends σ to `graph_sigma_iter`; adds per-point text label                   |
| `_on_sigma_completed`       | Draws corrected σ median line on `graph_sigma_iter` via `sigma_completed`    |
| `_on_seebeck_fit_ready`     | Plots V₁ vs V₂ scatter + fit line on `graph_fit`; adds graph to seebeck splitter |
| `_on_phase_changed`         | Switches `graph_stack` page: "sigma"→1, "seebeck"→2, "idle"→stay           |
| `_update_graph_placeholder` | Updates placeholder label text based on checkbox selection                    |
| `_toggle_graph_maximize`    | Uses `seebeck_graph_splitter`; handles 2 or 3 panels dynamically            |

#### Lifecycle

- `__init__` → `_build_top_bar()` → `_build_body()` → `_build_status_bar()` → `_connect_backend()` → `eurotherm.start()`
- `closeEvent` / `_on_exit` → `measurement_svc.stop()` → `eurotherm.stop()` → `app.quit()`
- `showEvent` → sets initial 50/50 splitter sizes (once)

#### Status bar design

- Right side: instrument dots + labels with **no separator widgets**
- Each instrument: 12 × 12 px dot (circle, border-radius 6 px) + 2 px margin-left + name label
- **20 px spacer** between each instrument group; 10 px spacer at far right
- No `|` between dot and label; no `QFrame` separators

---

### `gui/backend/eurotherm_service.py`  (251 lines) — COMPLETE

Thread-safe wrapper around `EurothermController`.

#### `_EurothermWorker` (QObject, lives on QThread)

| Signal                     | Type     | When                                    |
| -------------------------- | -------- | --------------------------------------- |
| `temperature_read`         | `float`  | Successful temperature read             |
| `temperature_read_failed`  | (none)   | Controller responded but value is None  |
| `set_point_reached`        | `float`  | Set-point accepted by controller        |
| `error_occurred`           | `str`    | Any exception during serial I/O         |
| `connection_changed`       | `bool`   | True on connect, False on disconnect    |

| Slot                     | What it does                                |
| ------------------------ | ------------------------------------------- |
| `connect_to_furnace()`   | Opens serial, emits one immediate read, starts polling |
| `disconnect_from_furnace()` | Stops polling, closes serial               |
| `set_temperature(float)` | Writes set-point via MODBUS                 |
| `set_ramp_rate(float)`   | Writes ramp rate via MODBUS                 |
| `read_temperature()`     | Reads PV, emits signal, reschedules via single-shot timer |

#### `EurothermService` (QObject, lives on GUI thread)

| Public method              | Effect                                            |
| -------------------------- | ------------------------------------------------- |
| `start()`                  | Starts QThread + emits `_request_connect`          |
| `stop()`                   | Emits `_request_disconnect`, `thread.quit()`, wait 3 s |
| `set_temperature(float)`   | Emits `_request_set_temp`                          |
| `set_ramp_rate(float)`     | Emits `_request_set_rate`                          |
| `read_temperature()`       | Emits `_request_read_temp`                         |

Private signals (`_request_connect`, `_request_disconnect`,
`_request_set_temp`, `_request_set_rate`, `_request_read_temp`) ensure
all calls are delivered via the worker thread's event loop (queued
connection, fully thread-safe).

#### Constants used

From `constants.py`:
- `EUROTHERM_COM_PORT = 5`  (COM5)
- `EUROTHERM_DEVICE_ADDRESS = 1`
- `EUROTHERM_BAUD_RATE = 9600`
- `EUROTHERM_TIMEOUT = 2.0`

Polling: `POLL_INTERVAL_MS = 1000` (1 second between reads)

---

### `gui/backend/measurement_service.py`  (~490 lines) — COMPLETE

Thread-safe wrapper that runs σ and Seebeck measurements on a background
QThread.  Mirrors exactly what `run_sigma.py`, `run_seebeck.py`, and
`run_combined.py` do in the terminal, but emits Qt signals instead of
printing to stdout.

#### `_QtLogHandler` (logging.Handler)

Custom handler that bridges Python's `logging` framework to Qt signals.
Attached to the file loggers returned by `create_single_measurement_structure()`
so measurement log messages also appear in the GUI log panel.

#### `MeasurementAborted` (Exception)

Sentinel exception raised when the abort flag is detected, enabling
clean unwinding through `try/except` blocks.

#### `_QtPlotBridge` (inner class, created at run-time inside `_run_seebeck`)

Duck-typed plotter replacement injected into the `SeebeckMeasurement`
instance.  Its `update(t, t1, t2, v1, v2)` method:
1. Emits `seebeck_data_point` signal with a dict `{"time", "T1", "T2", "V1", "V2"}`
2. Calls the original plotter's `update()` if it existed (fall-through)

This enables real-time graph updates in the GUI without touching the
core measurement code.

#### `_MeasurementWorker` (QObject, lives on QThread)

| Signal                     | Type           | When                                       |
| -------------------------- | -------------- | ------------------------------------------ |
| `log_message`              | `str`          | Concise message for the GUI log panel      |
| `status_message`           | `str`          | One-liner for the status bar               |
| `instrument_status`        | `(str, str)`   | (instrument name, state) e.g. ("Multimeter", "active") |
| `sigma_completed`          | `dict`         | σ measurement results                       |
| `seebeck_completed`        | `dict`         | Seebeck measurement results                 |
| `measurement_finished`     | `(bool, str, dict)` | (success, summary text, metadata dict) |
| `seebeck_data_point`       | `dict`         | Single Seebeck time-series point (real-time)|
| `sigma_data_point`         | `dict`         | Single σ iteration data (real-time)         |
| `seebeck_fit_ready`        | `dict`         | V₁/V₂ arrays + slope/intercept/R² for fit  |
| `phase_changed`            | `str`          | "sigma", "seebeck", or "idle"              |

| Method                      | What it does                                              |
| --------------------------- | --------------------------------------------------------- |
| `run(config)`               | Main entry — reads temp, creates folders, runs σ then Seebeck |
| `_install_abortable_sleep()`| Monkey-patches `time.sleep` with abort-aware version (0.25 s chunks); returns original |
| `_prepare_folders(…)`       | Creates output dirs + loggers; returns context tuple       |
| `_run_sigma(…)`             | Executes σ measurement (real or simulated); logs V1–V4 per iteration |
| `_run_seebeck(…)`           | Executes Seebeck measurement, injects `_QtPlotBridge`      |
| `_interruptible_sleep(secs)`| Sleeps in 0.5 s chunks, raises `MeasurementAborted` if flag set |
| `_check_abort(stage)`       | Raises `MeasurementAborted` if abort was requested         |
| `_set_instruments(state)`   | Emits status for PS + DAQ simultaneously                   |
| `_finalize_loggers(…)`      | Closes file loggers on failure / abort                     |
| `_make_logger(logger)`      | Attaches `_QtLogHandler` to a file logger                  |
| `request_abort()`           | Sets the `threading.Event`                                 |
| `reset_abort()`             | Clears the abort flag for a new run                        |

#### `MeasurementService` (QObject, lives on GUI thread)

| Public method     | Effect                                                   |
| ----------------- | -------------------------------------------------------- |
| `start(config)`   | Starts QThread if needed, emits `_request_run`           |
| `request_abort()` | Sets worker abort flag                                   |
| `stop()`          | Aborts + `thread.quit()` + wait 5 s (call on app exit)  |
| `is_running`      | Property — True if the worker thread is alive            |

Forwarded signals (re-emitted from worker to service):
`log_message`, `status_message`, `instrument_status`,
`measurement_finished`, `seebeck_data_point`, `sigma_data_point`,
`seebeck_fit_ready`, `phase_changed`.

#### Config dict schema (passed to `start()`)

```python
{
    "sample_name":     str,       # e.g. "MySample"
    "diameter":        float,     # mm
    "thickness":       float,     # mm
    "measure_sigma":   bool,
    "measure_seebeck": bool,
    "seebeck_time":    float,     # seconds (default 480)
    "simulation":      bool,      # True = use simulated instruments
}
```

#### Abort flow (instant abort design)

1. `request_abort()` sets a `threading.Event`
2. `_install_abortable_sleep()` replaces `time.sleep` globally with a
   version that sleeps in **0.25 s chunks** and raises `MeasurementAborted`
   as soon as the flag is set — this means any `time.sleep()` call inside
   `measure_sigma` or `SeebeckMeasurement` is also abort-aware
3. `_check_abort(stage)` is called between every major step
4. `MeasurementAborted` is caught in `run()` → instruments set to "idle",
   loggers finalized, `measurement_finished(False, "Aborted by user")` emitted
5. Original `time.sleep` is always restored in the `finally` block

#### Measurement sequence

1. Read current temperature (real or simulated)
2. Create folder structure via `output_manager.create_single_measurement_structure()`
   — temperature folder is named `{temperature:.1f}C` (e.g. `28.5C`)
3. If σ selected → `_run_sigma()` (real via `measure_sigma()` or simulated)
   — logs V1, V2, V3, V4, ΔV1, ΔV2, R1, R2, and σ per iteration
4. Safety pause (2 s, abort-aware) if both selected
5. If Seebeck selected → `_run_seebeck()` (real via `SeebeckMeasurement` or simulated)
   — injects `_QtPlotBridge` for real-time graph updates
6. Emit summary line + `measurement_finished`

---

### `gui/widgets/sample_info.py`  (~110 lines) — COMPLETE

`SampleInfoPanel(QGroupBox)` — "SAMPLE INFORMATION"

| Widget         | Type            | Range / Default         |
| -------------- | --------------- | ----------------------- |
| `name_input`   | `QLineEdit`     | Placeholder text        |
| `dia_input`    | `QDoubleSpinBox`| 0.001–100 mm, 2 dec     |
| `thk_input`    | `QDoubleSpinBox`| 0.001–50 mm, 2 dec      |

| Signal                              | When                                |
| ----------------------------------- | ----------------------------------- |
| `sample_changed(str, float, float)` | Any of the 3 fields change          |

| Getter              | Returns               |
| ------------------- | --------------------- |
| `get_sample_name()` | `str`                 |
| `get_diameter()`    | `float` (mm)          |
| `get_thickness()`   | `float` (mm)          |

---

### `gui/widgets/method_config.py`  (~240 lines) — COMPLETE

`MethodConfigPanel(QGroupBox)` — "METHOD CONFIGURATION"

#### Experiment mode (segmented toggle)
- **Current Temperature** (default) — single measurement at current temp
- **Temperature Cycle** — sweep with cycle settings

#### Cycle direction (radio buttons)
| Widget            | Label              |
| ----------------- | -------------------|
| `radio_heat_only` | Heating Only       |
| `radio_heat_cool` | Heating + Cooling  |

Radios are in a non-exclusive `QButtonGroup` with manual mutual
exclusion — allows all-unchecked when in "Current Temperature" mode.
Disabled when cycle mode is off.

#### Measurement selection (checkboxes)
| Widget              | Label                     |
| ------------------- | ------------------------- |
| `chk_seebeck`       | Seebeck Coefficient (S)   |
| `chk_conductivity`  | Electrical Conductivity (σ)|

#### Testing Mode
- `chk_testing`: QCheckBox "Testing Mode" — separated by a horizontal line
- `seebeck_time_spin`: QDoubleSpinBox (1.0–60.0 min, default 8.0, suffix " min")
- Hidden by default; shown when `chk_testing` is checked
- When active, `_on_run` uses `seebeck_time_min * 60` instead of the default 480 s

| Signal             | When                                |
| ------------------ | ----------------------------------- |
| `mode_changed(bool)` | Cycle mode toggled (True = cycle)  |
| `settings_changed()` | Any setting changes               |

| Getter           | Returns                                          |
| ---------------- | ------------------------------------------------ |
| `is_cycle_mode()`| `bool`                                           |
| `is_heating_only()` | `bool`                                        |
| `get_settings()` | `dict` with `cycle_mode`, `heating_only`, `measure_seebeck`, `measure_conductivity`, `testing_mode`, `seebeck_time_min` |

---

### `gui/widgets/temperature.py`  (~175 lines) — COMPLETE

`TemperatureProfilePanel(QGroupBox)` — "TEMPERATURE PROFILE"

#### Target row (always visible + enabled)

```
[target_spin 120px] [SET 54px]   Rate: [rate_spin 110px]
```

- `target_spin`: 25.0–1500.0 °C, default 350.0, 1 decimal
- `set_btn`: emits `set_temp_requested(target, rate)` on click
- `rate_spin`: 0.1–50.0 °C/min, default 10.0 — **always visible**

#### Cycle settings (disabled until cycle mode active)

| Row | Widgets                                  |
| --- | ---------------------------------------- |
| 0   | Start (25–1500 °C, def 50) &#124; Stop (25–1500 °C, def 200) |
| 1   | Step (1–200 °C, def 25)                  |

`_cycle_widgets` list = `[start_spin, stop_spin, step_spin]` — rate is
**not** in this list because it's always enabled.

| Signal                           | When                           |
| -------------------------------- | ------------------------------ |
| `set_temp_requested(float, float)` | SET clicked — (target, rate) |

| Getter         | Returns                                              |
| -------------- | ---------------------------------------------------- |
| `get_settings()` | `dict` with `target_temp`, `rate`, `start_temp`, `stop_temp`, `step` |

---

### `gui/widgets/graph_panel.py`  (~310 lines) — COMPLETE

`GraphPanel(QWidget)` — reusable pyqtgraph plot wrapper with optional
multi-curve mode.

Constructor: `GraphPanel(title, x_label, y_label, x_unit, y_unit, *, curves=None)`

- `curves`: optional `list[tuple[str, str]]` — `[(name, hex_colour), …]`
  If provided, multi-curve mode is activated with a legend.
  If omitted, single-curve mode (backward-compatible).
- Header (32 px): title + ⇓ download + ↺ reset + ⛶ maximize + ▾ collapse buttons
- Plot: dark background (`BG_PRIMARY`), grid, **right-click menu disabled**
- All 4 axes shown; top/right have no ticks (frame only)
- `_CURVE_COLORS` default palette defined for auto-colouring
- Crosshair tooltip shows **all curves' values** at the hovered x position
- Collapse/expand (▾/▸): hides the plot area, keeps header visible

| Signal                | When                    |
| --------------------- | ----------------------- |
| `maximize_requested()` | ⛶ button clicked       |

| Method                              | What it does                                              |
| ----------------------------------- | --------------------------------------------------------- |
| `append_point(x, y)`                | Single-curve mode: adds one data point                    |
| `append_to(curve_name, x, y)`       | Multi-curve mode: adds point to named curve               |
| `set_data(x, y)`                    | Single-curve mode: replaces entire dataset                |
| `set_data_named(curve_name, x, y)`  | Multi-curve mode: replaces dataset for a named curve      |
| `clear_data()`                      | Clears all curves + reference lines                       |
| `add_horizontal_line(y, pen, label)`| Adds a labelled InfiniteLine; tracked in `_ref_lines`     |
| `clear_reference_lines()`           | Removes all reference lines from the plot                 |
| `save_clean_png(path, width=1920)`  | Saves high-res PNG without crosshairs                     |
| `_on_download()`                    | Prompts user for path, calls `save_clean_png`             |
| `_toggle_collapse()`                | Hides/shows plot area (header stays visible)              |

Instances in MainWindow:
- `graph_sigma_iter`: "Conductivity (σ per Iteration)" — single curve
- `graph_seebeck_t`: "Temperature (T₁/T₂ vs Time)" — multi-curve `T₁`, `T₂`
- `graph_seebeck_v`: "Voltage (V₁/V₂ vs Time)" — multi-curve `V₁`, `V₂`
- `graph_fit`: "V₁ vs V₂ (Seebeck Fit)" — multi-curve `Data`, `Fit`

---

### `gui/widgets/log_panel.py`  (~75 lines) — COMPLETE

`LogPanel(QWidget)` — timestamped read-only log area.

- Header (24 px): "LOG" + Clear button (right-aligned, small)
- `QPlainTextEdit` (`#LogArea`), read-only, max 2000 blocks
- Monospace font (Consolas), dark background (`#111111`)

| Method          | What it does                                                       |
| --------------- | ------------------------------------------------------------------ |
| `append(str)`   | Prepends `[HH:MM:SS]` and scrolls down                            |
| `clear()`       | Clears all text — **resets `maximumBlockCount` to 0 before clear, then back to 2000** to avoid Qt bug where `appendPlainText` stops working after `clear()` |

| Widget              | Purpose                                           |
| ------------------- | ------------------------------------------------- |
| `_clear_btn`        | `QPushButton` (`#LogClearButton`) — clears the log |

**Qt quirk fixed**: calling `QPlainTextEdit.clear()` while
`maximumBlockCount > 0` causes subsequent `appendPlainText` calls to
silently no-op.  Fix: set `maximumBlockCount = 0`, call `clear()`,
then restore `maximumBlockCount = 2000`.

---

## 4. What Works End-to-End

| Feature                              | Status | Notes                                                                  |
| ------------------------------------ | ------ | ---------------------------------------------------------------------- |
| SET temperature button               | ✅     | Sends ramp rate then target to Eurotherm                               |
| Current temperature display          | ✅     | 1 s polling via single-shot chain                                      |
| Heartbeat logging (30 s)             | ✅     | Every 30th successful read logged                                      |
| Failed-read warning                  | ✅     | Immediate log + status bar update                                      |
| Connection state in status bar       | ✅     | "Eurotherm connected" / "disconnected"                                 |
| Ramp rate beside SET button          | ✅     | Always visible, not gated by cycle mode                                |
| Cycle settings enable/disable        | ✅     | Gated by method_panel.mode_changed signal                              |
| RUN button validation                | ✅     | 5-condition check with detailed tooltip                                |
| RUN button tooltip when disabled     | ✅     | `_RunButton` subclass forwards ToolTip event                           |
| Panel collapse / expand              | ✅     | Arrow strip + auto-collapse below 200 px                               |
| Graph maximize / restore             | ✅     | ⛶ button toggles single-graph view                                    |
| Exit with measurement guard          | ✅     | Confirmation dialog if measurement running                             |
| Eurotherm cleanup on close           | ✅     | `eurotherm.stop()` in `closeEvent` + `_on_exit`                       |
| σ measurement execution              | ✅     | Real + simulated, results saved to CSV                                 |
| Seebeck measurement execution        | ✅     | Real + simulated, results saved to CSV                                 |
| Combined σ + Seebeck                 | ✅     | σ always runs first, 2 s safety pause between                         |
| Measurement abort (instant)          | ✅     | `time.sleep` monkey-patched; abort fires within 0.25 s of any sleep   |
| Log panel Clear button               | ✅     | Small "Clear" button in LOG header row                                 |
| Log clear bug fixed                  | ✅     | `maximumBlockCount` reset workaround prevents silent no-op             |
| Instrument status indicators         | ✅     | 3 coloured 12 px dots in status bar (Eurotherm, PS, DAQ)              |
| Measurement service cleanup          | ✅     | `measurement_svc.stop()` in `closeEvent` + `_on_exit`                 |
| **Decimal folder naming**            | ✅     | Temperature folders named `{temp:.1f}C` (e.g. `28.5C`)               |
| **Completion summary dialog**        | ✅     | `_MeasurementSummaryDialog` shown on `measurement_finished`            |
| **Detailed sigma iteration logging** | ✅     | V1–V4, ΔV1/ΔV2, R1/R2, σ per iteration in log panel                  |
| **Pointer cursors on dialog buttons**| ✅     | All dialog buttons (`Cancel`, `Start Run`, `OK`) use `PointingHandCursor` |
| **Status bar redesign**              | ✅     | 12 px dots, 20 px spacing, no separators, 2 px dot-label gap          |
| **Real-time Seebeck graphs**         | ✅     | T₁/T₂ vs Time and V₁/V₂ vs Time, fed by `seebeck_data_point` signal  |
| **Real-time σ iteration graph**      | ✅     | σ per iteration with per-point labels, corrected σ median line via `sigma_completed` |
| **Dynamic right panel (QStackedWidget)** | ✅ | Placeholder → σ graph → Seebeck view, switched by `phase_changed`     |
| **V₁ vs V₂ Seebeck fit graph**      | ✅     | Scatter + linear fit, added to Seebeck splitter on `seebeck_fit_ready` |
| **Per-iteration σ CSV**              | ✅     | CSV with V1–V4, ΔV, R, σ per iteration via `save_iteration_data_to_csv` |
| **Graph tooltip all curves**         | ✅     | Tooltip shows ALL curves' values at hovered x position                 |
| **Testing mode**                     | ✅     | Checkbox + adjustable Seebeck time (1–60 min), hidden by default       |
| **Confirm dialog with temperature**  | ✅     | Shows current temp or cycle points before starting run                 |
| **Confirm dialog DATA PATH**        | ✅     | Shows output directory in confirm dialog; defaults to `./data/`        |
| **Summary dialog with metadata**     | ✅     | Shows temperature, σ time, Seebeck time, total time, data path         |
| **Graph Download button (⇓)**       | ✅     | Each graph header has download button → save clean PNG via dialog      |
| **Graph Reset View button (↺)**     | ✅     | Each graph header has reset button → auto-range                        |
| **Graph Collapse/Expand (▾/▸)**     | ✅     | Each graph header has collapse button → hides plot, keeps header       |
| **pyqtgraph right-click disabled**   | ✅     | `setMenuEnabled(False)` on all graph PlotWidgets                       |
| **Sigma plot saved (matplotlib)**    | ✅     | `_save_sigma_iteration_plot()` called after σ measurement in both paths |
| **Seebeck fit plot saved**           | ✅     | `_save_seebeck_fit_plot()` called after seebeck in both paths          |
| **Summary data tuple alignment**     | ✅     | `_summary_sigma` and `_summary_seebeck` use `(temp, value)` tuples     |
| **sigma_completed signal wired**     | ✅     | Connected in `_connect_backend` → `_on_sigma_completed` draws median   |

---

## 5. What's NOT Implemented Yet (TODOs)

| Area                               | Location in code                         | What's needed                                                    |
| ---------------------------------- | ---------------------------------------- | ---------------------------------------------------------------- |
| **Temperature cycle execution**    | `_on_run()` in main_window.py            | `measure_sigma` and `SeebeckMeasurement` are wired for current-temp mode only; cycle sweeps (heat, cool) not implemented yet |
| **σ vs T graph feed**              | —                                        | Post-sweep summary σ vs T plot not yet implemented               |
| **Simulation toggle in UI**        | `_on_run()` in main_window.py            | `"simulation": True` is hardcoded — needs a checkbox or setting  |
| **Settings persistence**           | —                                        | No save/load of user preferences or last-used settings           |

---

## 6. External Dependencies Used by GUI

| Package     | Used for                                   |
| ----------- | ------------------------------------------ |
| `PySide6`   | All GUI: widgets, signals, QThread, layouts|
| `pyqtgraph` | Real-time plotting in GraphPanel           |
| `numpy`     | Array ops in GraphPanel.append_point       |
| `pyserial`  | Serial communication (in EurothermController) |
| `minimalmodbus` | MODBUS protocol (in EurothermController) — *check if actually used or if raw serial is used* |

---

## 7. `EurothermController` API (from `eurotherm_control.py`)

The service wraps this class.  Key methods:

| Method                    | Returns          | What it does                              |
| ------------------------- | ---------------- | ----------------------------------------- |
| `connect()`               | `bool`           | Opens COM port, returns True on success   |
| `disconnect()`            | `None`           | Closes serial port                        |
| `is_connected()`          | `bool`           | Checks `_connected` flag                  |
| `read_temperature()`      | `Optional[float]`| Reads PV register (current temp in °C)    |
| `set_temperature(float)`  | `bool`           | Writes SP register                        |
| `set_ramp_rate(float)`    | `bool`           | Writes ramp rate register (°C/min)        |
| `wait_for_stability(...)`| —                 | Blocking wait — NOT used by GUI           |

MODBUS registers: PV=1, SP=2, OutputPower=3, RampRate=35, AutoManual=273.
Protocol: MODBUS RTU, 9600 8N1, CRC-16, inter-frame delay 4 ms.

---

## 8. Constants Relevant to GUI (`constants.py`)

```python
EUROTHERM_COM_PORT = 5
EUROTHERM_DEVICE_ADDRESS = 1
EUROTHERM_BAUD_RATE = 9600
EUROTHERM_TIMEOUT = 2.0              # seconds

EUROTHERM_STABILITY_TOLERANCE = 1.0  # °C
EUROTHERM_STABILITY_TIME = 60.0      # seconds
EUROTHERM_STABILITY_TIMEOUT = 1800.0 # 30 min
EUROTHERM_CHECK_INTERVAL = 5.0       # seconds

DEFAULT_START_TEMP = 50.0            # °C
DEFAULT_END_TEMP = 200.0             # °C
DEFAULT_TEMP_STEP = 25.0             # °C
DEFAULT_RAMP_RATE = 10.0             # °C/min

DEFAULT_SAMPLE_THICKNESS = 2.1       # mm
DEFAULT_SAMPLE_DIAMETER = 15         # mm
```

---

## 9. How to Run

```bash
# From project root
python -m gui.app
# or
python gui/app.py
```

---

## 10. Quick Verification Commands

```bash
# Check imports are clean (no runtime errors)
python -c "from gui.main_window import MainWindow; print('OK')"

# Check eurotherm service imports
python -c "from gui.backend.eurotherm_service import EurothermService; print('OK')"

# Check measurement service imports
python -c "from gui.backend.measurement_service import MeasurementService; print('OK')"

# Check backend package exports
python -c "from gui.backend import EurothermService, MeasurementService; print('OK')"
```

---

## 11. Latest Changes (most recent session — 2026-03-01)

All 8 requests were implemented. Files changed:

### 1. `output_manager.py` — decimal folder naming
- `create_single_measurement_structure()` and `create_temperature_folder()`
  now use `f"{temperature:.1f}C"` instead of `f"{int(round(temperature))}C"`
- Example: `28.5C` instead of `28C` or `29C`

### 2. `gui/main_window.py` — summary dialog + confirm dialog cursors + status bar + graphs

**`_MeasurementSummaryDialog`** (new inner class):
- Shows ✔ (green `SUCCESS`) or ✖ (red `DANGER`) icon depending on success
- Displays the summary string (e.g. `σ = 1.23e+03 S/cm │ S = 45.67 µV/K`)
- "OK" button with `Qt.PointingHandCursor`
- Called from `_on_measurement_finished()` after run completes

**`_MeasurementConfirmDialog`** cursor fix:
- "Cancel" and "Start Run" buttons both now set `Qt.PointingHandCursor`

**Status bar redesign** (`_build_status_bar` + `_refresh_instrument_dot`):
- Dot size: **12 × 12 px** (was 8 × 8 px), border-radius 6 px
- **20 px QWidget spacers** between instrument groups (no `QFrame` separators)
- **10 px spacer** at far right
- **2 px `margin-left`** on instrument labels (tiny gap between dot and name)
- No `|` character between dot and label

**Graphs replaced**:
- `graph_seebeck` → "Temperature (T₁/T₂ vs Time)", curves: `T₁` (#E06B67), `T₂` (#5B9BD5)
- `graph_sigma` → "Voltage (V₁/V₂ vs Time)", curves: `V₁` (#4EC94E), `V₂` (#F0A500)
- Both cleared when `_set_running(True)` is called
- Fed by `_on_seebeck_data_point(data)`:
  - Converts `time` (seconds) → minutes
  - Converts `V` (volts) → µV (`× 1e6`)
  - Calls `graph_seebeck.append_to("T₁", t_min, data["T1"])` etc.

**Signal wiring added**:
```python
measurement_svc.seebeck_data_point.connect(self._on_seebeck_data_point)
```

### 3. `gui/backend/measurement_service.py` — abort + real-time bridge + refactor

**`_install_abortable_sleep()`** (new method):
- Replaces `time.sleep` globally with a version that sleeps in 0.25 s
  chunks, checking the abort flag after each chunk
- Returns the original `time.sleep` so it can be restored in `finally`
- Means **every** `time.sleep()` inside `measure_sigma` or
  `SeebeckMeasurement` is automatically abort-aware

**`_prepare_folders()`** (new method, extracted from `run()`):
- Creates output dirs, initialises loggers, logs opening line
- Reduces `run()` cognitive complexity from 17 → ≤15

**`_QtPlotBridge`** (new inner class, created in `_run_seebeck`):
- Duck-typed plotter replacement injected into `SeebeckMeasurement`
- `update(_, t, t1, t2, v1, v2)` emits `seebeck_data_point` dict signal

**`seebeck_data_point = Signal(dict)`** added to both worker and service.

**`_run_sigma`** now logs per iteration:
```
  Iter N | V1=…µV  V2=…µV  ΔV=…µV  R=…Ω  σ=…S/cm
  Iter N | V3=…µV  V4=…µV  ΔV=…µV  R=…Ω
```

**Folder name** uses `f"{current_temp:.1f}C"` in CSV filename.

### 4. `gui/widgets/graph_panel.py` — multi-curve support

- Constructor accepts optional `curves: list[tuple[str, str]]`
- If provided: creates `self._named_curves` dict, adds pyqtgraph legend
- `append_to(curve_name, x, y)` for multi-curve data
- `clear_data()` clears all named curves + legacy single curve
- Backward compatible: `append_point()` / `set_data()` still work

### 5. `gui/widgets/log_panel.py` — clear bug fix

- `clear()` now: sets `maximumBlockCount = 0`, calls `clear()`, sets
  `maximumBlockCount = 2000`
- Fixes Qt quirk where `appendPlainText` silently stops working after
  `clear()` if `maximumBlockCount > 0`

### 6. `measure_sigma.py` — detailed iteration logging

- VDP loop now calls `_log()` with V1, V2, ΔV1, R1 and V3, V4, ΔV2, R2
  and σ per iteration
- Summary remains unchanged

### 7. `simulation.py` — simulated voltage logging

- `simulate_sigma_measurement()` generates V1–V4 per iteration
- Logs them via `logger.info()` in the same format as real measurements
- Note that only edit the simulation and consider them when told, otherwise always keep simulation out of picture

### 8. `gui/styles.py` — dot size update

- `.InstrumentDot`: width/height `12px`, border-radius `6px` (was `8px`/`4px`)

---

## 12. Previous Session Changes (still in effect)

1. **MeasurementService created** — QThread-based service, `_QtLogHandler`,
   `MeasurementAborted`, abort via `threading.Event`.
2. **Log panel Clear button** — `#LogClearButton` styled in `styles.py`.
3. **Instrument status indicators** — 3 coloured dots, managed by
   `_on_instrument_status` / `_refresh_instrument_dot`.
4. **Run button wired** — `_on_run()` shows confirm dialog, calls
   `measurement_svc.start(config)`.
5. **Abort button wired** — `_on_abort()` shows confirmation dialog,
   calls `measurement_svc.request_abort()`.
6. **Exit cleanup** — `closeEvent` calls both `measurement_svc.stop()` and
   `eurotherm.stop()`.
7. **Thread-safe EurothermService** — private signals, single-shot polling,
   `set_ramp_rate` slot, rate spinner always visible.

---

## 13. Known Quirks / Design Decisions

- **`_RunButton`**: Subclasses `QPushButton` only to override tooltip
  behaviour for disabled state.  Could be replaced with an event filter.
- **Cycle direction radios**: Use a *non-exclusive* `QButtonGroup` with
  manual mutual exclusion so all can be unchecked in current-temp mode.
- **Scroll area right margin**: 20 px to avoid content touching the
  scrollbar.
- **Graph maximize**: Toggles by collapsing all *other* panels in
  `seebeck_graph_splitter`; handles 2 or 3 panels dynamically.
- **QStackedWidget right panel**: 3 pages — placeholder (index 0),
  σ iteration graph (index 1), Seebeck view with splitter (index 2).
  `phase_changed` signal drives page switching.
- **Fit graph late-add**: `graph_fit` is created at startup but only
  added to `seebeck_graph_splitter` when `seebeck_fit_ready` fires.
  Removed from splitter (`setParent(None)`) on next run start.
- **Status bar**: `status_label` for one-line messages + 3 instrument
  dots (permanent widgets) on the right.  No `QFrame` separators — just
  QWidget spacers.
- **Log panel**: 2000-block limit prevents memory growth in long runs.
  `clear()` uses the `maximumBlockCount = 0` workaround (Qt quirk).
- **Simulation hardcoded**: `"simulation": True` in `_on_run()` — must
  be exposed as a UI toggle before real hardware use.
- **Instrument dots inline-styled**: `_refresh_instrument_dot` sets
  `setStyleSheet(…)` directly because class-based dynamic property
  changes require `polish()` / `unpolish()` which is fragile.
- **`_QtPlotBridge`**: Created as a local class inside `_run_seebeck` so
  it can close over `_worker_ref` and `_orig_update` without being a
  module-level class.  Uses `_` as the `self` parameter name with
  `# noqa: N805` to satisfy linting.
- **`time.sleep` monkey-patch**: Installed per-run (not globally at import
  time) and always restored in `finally` so it cannot leak between runs or
  affect other threads.

---

## 14. Latest Changes (most recent session — 2026-03-03)

Bug-fix and quality session.  Files changed:

### 1. `gui/widgets/graph_panel.py` — new header buttons + collapse
- **Right-click disabled**: `self._plot.setMenuEnabled(False)` removes built-in pyqtgraph Export menu.
- **Download button (⇓)**: opens `QFileDialog` → saves clean PNG via `save_clean_png()`.
- **Reset View button (↺)**: calls `self._plot.autoRange()`.
- **Collapse/Expand button (▾/▸)**: `_toggle_collapse()` hides/shows the plot widget; header stays visible.
- `_build_ui()` stores plot widget as `self._plot_widget` for collapse toggling.

### 2. `gui/main_window.py` — median line fix + data alignment + confirm dialog
- **Sigma median line fix**: Removed broken `iteration == 5` median code from `_on_sigma_data_point()`. Added `_on_sigma_completed(results)` that uses `corr_sigma` from `sigma_completed` signal to draw the correct geometry-corrected median line.
- **`sigma_completed` signal wired**: Connected in `_connect_backend()` → `_on_sigma_completed`.
- **Summary data alignment**: Replaced 3 parallel lists (`_summary_temps`, `_summary_sigma`, `_summary_seebeck`) with 2 independent tuple lists: `_summary_sigma: list[tuple[float, float]]` and `_summary_seebeck: list[tuple[float, float]]`. Eliminates misalignment when measurements differ per temperature point.
- **`_on_cycle_point_completed`**: Updated to append `(temp, value)` tuples.
- **`_export_cycle_summary`**: Updated to unpack tuples instead of `zip()`.
- **Confirm dialog DATA PATH**: `_MeasurementConfirmDialog` now accepts `output_dir` parameter and displays it as a "DATA PATH" section (defaults to `./data/`).

### 3. `gui/backend/measurement_service.py` — plot saving calls
- **`_save_sigma_iteration_plot()`**: Now called after σ measurement in both single-temp and cycle paths (was dead code).
- **`_save_seebeck_fit_plot()`**: Now called after Seebeck `_save_seebeck_time_series_plots()` in both paths (was dead code). All 3 Seebeck plots are now saved (time-series T, time-series V, and fit).

---

## 15. Previous Session Changes (2026-03-02)

6 feature requests implemented.  Files changed:

### 1. `gui/widgets/graph_panel.py` — tooltip + utility methods
- **Tooltip rewrite**: `_on_mouse_moved` now shows ALL curves' values at
  the nearest x position (header line with x-axis label, one line per
  curve with coloured name and value).  Single-curve mode uses `y_label`
  as display name.
- **`set_data_named(curve_name, x, y)`**: Replaces data for a specific
  named curve (multi-curve mode).
- **`add_horizontal_line(y, pen, label)`**: Adds a labelled
  `InfiniteLine`; tracked in `self._ref_lines`.
- **`clear_reference_lines()`**: Removes all reference lines.
- **`clear_data()`** now also calls `clear_reference_lines()`.

### 2. `gui/widgets/method_config.py` — testing mode
- Added horizontal separator line below measurement checkboxes.
- **`chk_testing`**: QCheckBox "Testing Mode".
- **`seebeck_time_spin`**: QDoubleSpinBox (1.0–60.0 min, default 8.0,
  suffix " min", width 100 px).  Hidden by default; shown when testing
  mode is checked.
- `get_settings()` now includes `"testing_mode"` and `"seebeck_time_min"`.

### 3. `measure_sigma.py` — iteration data + CSV
- **`progress_callback`** parameter added to `measure_sigma()` — called
  with a dict per VDP iteration containing `iteration, v1, v2, v3, v4,
  delta_v1, delta_v2, R1, R2, sigma`.
- **`iteration_results`** list collects all iteration dicts; added to
  the results dict under `"iterations"`.
- **`save_iteration_data_to_csv(results, sample_name, output_folder)`**:
  Saves CSV with columns: Iteration, V1(V), V2(V), V3(V), V4(V),
  Delta_V1(V), Delta_V2(V), R1(Ohm), R2(Ohm), Sigma(S/cm).

### 4. `gui/backend/measurement_service.py` — new signals + timing
- **3 new signals** on worker + service: `sigma_data_point(dict)`,
  `seebeck_fit_ready(dict)`, `phase_changed(str)`.
- **`measurement_finished`** signature changed: `Signal(bool, str, dict)`.
  Third argument is metadata dict.
- **Timing**: `_t_run_start`, `_sigma_elapsed`, `_seebeck_elapsed`,
  `_current_temp`, `_data_path` tracked during run.  Metadata dict
  includes `temperature, data_path, sigma_elapsed, seebeck_elapsed,
  total_elapsed`.
- **`_run_sigma`**: emits `phase_changed("sigma")`, creates a
  `_sigma_progress` callback that emits `sigma_data_point`, passes it
  to `measure_sigma()`.  Calls `save_iteration_data_to_csv()` after
  the main CSV save.
- **`_run_seebeck`**: emits `phase_changed("seebeck")`, after results
  emits `seebeck_fit_ready` with V1/V2 arrays (µV), slope, intercept,
  adj_r_square, seebeck values.
- **`run()`** emits `phase_changed("idle")` at end.

### 5. `gui/main_window.py` — complete UI overhaul
- **Imports**: added `pyqtgraph as pg`, `QStackedWidget`.
- **`_MeasurementConfirmDialog`**: accepts `current_temp` kwarg; adds
  TEMPERATURE section showing live temp or cycle temperature points.
- **`_MeasurementSummaryDialog`**: accepts `metadata` kwarg; adds
  DETAILS section with temperature, σ time, Seebeck time, total time,
  data path.  Uses `_add_row` static method.
- **Right panel**: replaced `graph_splitter` + 2 fixed graphs with:
  - `QStackedWidget` (`graph_stack`) with 3 pages:
    - Page 0: placeholder label with dynamic text
    - Page 1: `graph_sigma_iter` (σ per Iteration, single curve)
    - Page 2: `seebeck_graph_splitter` with `graph_seebeck_t` (T₁/T₂),
      `graph_seebeck_v` (V₁/V₂), and `graph_fit` (V₁ vs V₂, added at
      Seebeck end)
- **New signals connected**: `sigma_data_point`, `seebeck_fit_ready`,
  `phase_changed`, `settings_changed` → `_update_graph_placeholder`.
- **`_on_run`**: passes `current_temp` to confirm dialog; uses testing
  mode for seebeck time if enabled.
- **`_on_measurement_finished`**: new signature `(success, summary,
  metadata)`, passes metadata to summary dialog.
- **`_set_running`**: clears all 4 graphs; removes fit graph from
  splitter if previously added.
- **`_on_seebeck_data_point`**: feeds `graph_seebeck_t` + `graph_seebeck_v`.
- **`_on_sigma_data_point`**: appends σ to `graph_sigma_iter`; adds
  median reference line after iteration 5.
- **`_on_seebeck_fit_ready`**: plots V₁ vs V₂ scatter + fit line on
  `graph_fit`; adds annotation with S and adj R²; adds graph to splitter.
- **`_on_phase_changed`**: switches `graph_stack` page (sigma→1,
  seebeck→2, idle stays).
- **`_update_graph_placeholder`**: updates placeholder text based on
  measurement checkbox selection.
- **`_toggle_graph_maximize`**: rewritten for N-panel `seebeck_graph_splitter`.
