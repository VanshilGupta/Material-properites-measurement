"""
Eurotherm Temperature Test Script

Standalone script to:
1. Connect to the Eurotherm controller
2. Set a target temperature and ramp rate
3. Monitor the temperature in real-time
4. Verify that the furnace reaches the desired temperature
5. Optionally cool back down to a safe temperature

Usage:
    python test_eurotherm_temp.py
"""

import time
import sys
import logging
from datetime import datetime
from pathlib import Path

from eurotherm_control import EurothermController
from constants import (
    EUROTHERM_COM_PORT,
    EUROTHERM_DEVICE_ADDRESS,
    EUROTHERM_BAUD_RATE,
    EUROTHERM_TIMEOUT,
    EUROTHERM_STABILITY_TOLERANCE,
    EUROTHERM_STABILITY_TIME,
    EUROTHERM_STABILITY_TIMEOUT,
    EUROTHERM_CHECK_INTERVAL,
    DEFAULT_RAMP_RATE,
)

# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging() -> logging.Logger:
    """Create a logger that writes to both console and a log file."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%d-%m-%Y_%H%M%S")
    log_file = log_dir / f"eurotherm_temp_test_{timestamp}.log"

    logger = logging.getLogger("EurothermTempTest")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
    )
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info(f"Log file: {log_file}")
    return logger


# =============================================================================
# User Input Helpers
# =============================================================================

def get_user_inputs() -> dict:
    """Prompt the user for test parameters."""
    print("\n" + "=" * 60)
    print("   EUROTHERM TEMPERATURE TEST")
    print("=" * 60)

    try:
        com_port = int(
            input(f"  COM port number [default: {EUROTHERM_COM_PORT}]: ").strip()
            or str(EUROTHERM_COM_PORT)
        )
    except ValueError:
        com_port = EUROTHERM_COM_PORT

    try:
        target_temp = float(input("  Target temperature (°C): ").strip())
    except ValueError:
        print("  [!] Invalid input – please enter a number.")
        sys.exit(1)

    try:
        ramp_rate = float(
            input(f"  Ramp rate (°C/min) [default: {DEFAULT_RAMP_RATE}]: ").strip()
            or str(DEFAULT_RAMP_RATE)
        )
    except ValueError:
        ramp_rate = DEFAULT_RAMP_RATE

    try:
        tolerance = float(
            input(
                f"  Stability tolerance (°C) [default: {EUROTHERM_STABILITY_TOLERANCE}]: "
            ).strip()
            or str(EUROTHERM_STABILITY_TOLERANCE)
        )
    except ValueError:
        tolerance = EUROTHERM_STABILITY_TOLERANCE

    try:
        stable_time = float(
            input(
                f"  Stability hold time (s) [default: {EUROTHERM_STABILITY_TIME}]: "
            ).strip()
            or str(EUROTHERM_STABILITY_TIME)
        )
    except ValueError:
        stable_time = EUROTHERM_STABILITY_TIME

    try:
        timeout = float(
            input(
                f"  Max wait / timeout (s) [default: {EUROTHERM_STABILITY_TIMEOUT}]: "
            ).strip()
            or str(EUROTHERM_STABILITY_TIMEOUT)
        )
    except ValueError:
        timeout = EUROTHERM_STABILITY_TIMEOUT

    cooldown_input = (
        input("  Cool down to room temp after test? (y/n) [default: y]: ")
        .strip()
        .lower()
    )
    cooldown = cooldown_input != "n"

    params = {
        "com_port": com_port,
        "target_temp": target_temp,
        "ramp_rate": ramp_rate,
        "tolerance": tolerance,
        "stable_time": stable_time,
        "timeout": timeout,
        "cooldown": cooldown,
    }

    print("\n" + "-" * 60)
    print("  Configuration Summary:")
    print(f"    COM Port         : COM{params['com_port']}")
    print(f"    Target Temp      : {params['target_temp']} °C")
    print(f"    Ramp Rate        : {params['ramp_rate']} °C/min")
    print(f"    Tolerance        : ±{params['tolerance']} °C")
    print(f"    Stable Hold Time : {params['stable_time']} s")
    print(f"    Timeout          : {params['timeout']} s")
    print(f"    Cool Down After  : {'Yes' if params['cooldown'] else 'No'}")
    print("-" * 60)

    confirm = input("  Proceed? (y/n) [default: y]: ").strip().lower()
    if confirm == "n":
        print("  Aborted by user.")
        sys.exit(0)

    return params


# =============================================================================
# Live Monitoring
# =============================================================================

def monitor_temperature(
    controller: EurothermController,
    target: float,
    tolerance: float,
    stable_time: float,
    timeout: float,
    check_interval: float,
    logger: logging.Logger,
) -> bool:
    """
    Monitor temperature rise and verify stability at target.

    Prints a live dashboard to the console and logs every reading.

    Returns True if the target was reached and held, False on timeout.
    """
    logger.info(
        f"Monitoring started — target {target}°C  ±{tolerance}°C  "
        f"hold {stable_time}s  timeout {timeout}s"
    )

    start_time = time.time()
    stable_start = None
    reading_count = 0

    print("\n" + "=" * 60)
    print("  LIVE TEMPERATURE MONITOR  (Ctrl+C to abort)")
    print("=" * 60)
    print(f"  {'Time (s)':>10}  {'Current (°C)':>14}  {'Setpoint (°C)':>14}  {'Status'}")
    print("-" * 60)

    try:
        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout:
                print()
                logger.error(
                    f"TIMEOUT after {elapsed:.0f}s — temperature did NOT stabilize."
                )
                return False

            current_temp = controller.read_temperature()
            reading_count += 1

            if current_temp is None:
                logger.warning("Could not read temperature — retrying…")
                time.sleep(check_interval)
                continue

            # Only read setpoint after a successful temperature read so we
            # don't waste ~2 s in a timeout when the bus is unresponsive.
            setpoint = controller.read_setpoint()

            deviation = abs(current_temp - target)
            sp_str = f"{setpoint:.1f}" if setpoint is not None else "N/A"

            # Determine status
            if deviation <= tolerance:
                if stable_start is None:
                    stable_start = time.time()
                stable_elapsed = time.time() - stable_start

                if stable_elapsed >= stable_time:
                    status = "✓ STABLE"
                    line = (
                        f"  {elapsed:>10.1f}  {current_temp:>14.2f}  {sp_str:>14}  {status}"
                    )
                    print(f"\r{line}")
                    logger.info(line.strip())
                    logger.info(
                        f"SUCCESS — Temperature held at {current_temp:.2f}°C "
                        f"for {stable_elapsed:.0f}s  (readings: {reading_count})"
                    )
                    return True
                else:
                    status = f"Stabilizing ({stable_elapsed:.0f}/{stable_time:.0f}s)"
            else:
                stable_start = None
                if current_temp < target:
                    status = "Heating ↑"
                else:
                    status = "Cooling ↓"

            line = (
                f"  {elapsed:>10.1f}  {current_temp:>14.2f}  {sp_str:>14}  {status}"
            )
            # Overwrite the same console line for a clean dashboard feel
            print(f"\r{line}", end="", flush=True)
            logger.debug(line.strip())

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\n\n  [!] Monitoring aborted by user (Ctrl+C).")
        logger.warning("Monitoring aborted by user (Ctrl+C).")
        return False


# =============================================================================
# Main Routine
# =============================================================================

def main():
    logger = setup_logging()
    params = get_user_inputs()

    # --- Connect -----------------------------------------------------------
    controller = EurothermController(
        com_port=params["com_port"],
        device_address=EUROTHERM_DEVICE_ADDRESS,
        baud_rate=EUROTHERM_BAUD_RATE,
        timeout=EUROTHERM_TIMEOUT,
    )
    controller.set_logger(logger)

    print("\n[1/4] Connecting to Eurotherm …")
    if not controller.connect():
        logger.error("Could not connect to the Eurotherm. Exiting.")
        sys.exit(1)

    # --- Print initial status ------------------------------------------------
    print("\n[2/4] Reading initial status …")
    status = controller.get_status()
    logger.info("Initial controller status:")
    for key, value in status.items():
        display = f"{value:.2f}" if isinstance(value, float) else str(value)
        logger.info(f"  {key}: {display}")
        print(f"  {key}: {display}")

    initial_temp = status.get("temperature")
    if initial_temp is not None:
        print(f"\n  Current furnace temperature: {initial_temp:.2f} °C")
    else:
        logger.warning("Could not read initial temperature – proceeding anyway.")

    # --- Ensure AUTO mode, set ramp rate and target temp ---------------------
    print(f"\n[3/4] Setting ramp rate to {params['ramp_rate']} °C/min and target to {params['target_temp']} °C …")

    if not controller.is_auto_mode():
        logger.info("Switching to AUTO (PID) mode …")
        controller.set_auto_mode()
        time.sleep(0.5)

    if not controller.set_ramp_rate(params["ramp_rate"]):
        logger.error("Failed to set ramp rate.")

    if not controller.set_temperature(params["target_temp"]):
        logger.error("Failed to set target temperature. Exiting.")
        controller.disconnect()
        sys.exit(1)

    # Verify the setpoint was accepted
    time.sleep(0.5)
    readback_sp = controller.read_setpoint()
    if readback_sp is not None:
        logger.info(f"Setpoint readback: {readback_sp:.2f} °C")
    else:
        logger.warning("Could not read back setpoint.")

    # --- Monitor & wait for stability ----------------------------------------
    print("\n[4/4] Monitoring temperature …")
    reached = monitor_temperature(
        controller=controller,
        target=params["target_temp"],
        tolerance=params["tolerance"],
        stable_time=params["stable_time"],
        timeout=params["timeout"],
        check_interval=EUROTHERM_CHECK_INTERVAL,
        logger=logger,
    )

    # --- Result --------------------------------------------------------------
    print("\n" + "=" * 60)
    if reached:
        print("  ✓ RESULT: Temperature REACHED and STABLE at target.")
        logger.info("TEST PASSED — target temperature reached and stable.")
    else:
        print("  ✗ RESULT: Temperature did NOT reach / stabilize at target.")
        logger.error("TEST FAILED — target temperature NOT reached or NOT stable.")
    print("=" * 60)

    # --- Cool-down -----------------------------------------------------------
    if params["cooldown"]:
        cooldown_temp = 30.0  # °C — safe idle temperature
        print(f"\n  Cooling down — setting target to {cooldown_temp} °C …")
        logger.info(f"Setting cooldown target to {cooldown_temp} °C.")
        controller.set_temperature(cooldown_temp)
        # We don't wait for full cooldown; just set the setpoint and let it coast

    # --- Disconnect ----------------------------------------------------------
    controller.disconnect()
    print("\n  Done. Check the log file in /logs for full details.\n")


if __name__ == "__main__":
    main()
