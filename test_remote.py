"""
Remote Instrument Test Script
==============================
Runs against instrument_server.py on the lab PC.
Tests every available endpoint and prints pass/fail with debug info.

Usage:
    python test_remote.py              # runs all tests
    python test_remote.py eurotherm    # runs only eurotherm tests
    python test_remote.py daq          # runs only DAQ tests
    python test_remote.py ps           # runs only power supply tests
"""

import sys
import json
import time
import requests

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "http://100.109.129.26:8765"
TOKEN    = "vg@123"
HEADERS  = {"X-Token": TOKEN}
TIMEOUT  = 15   # seconds per request

# ── Counters ──────────────────────────────────────────────────────────────────
_passed = 0
_failed = 0
_skipped = 0


def _fmt_body(data) -> str:
    """Pretty-print response body (truncated)."""
    try:
        s = json.dumps(data, indent=None)
        return s[:200] + ("..." if len(s) > 200 else "")
    except Exception:
        return str(data)[:200]


def section(title: str):
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


def test(name: str, method: str, endpoint: str,
         body=None, expect_status: int = 200,
         warn_on_fail: bool = False) -> dict | None:
    """
    Execute one HTTP test.
    Returns the parsed JSON response on success, None on failure.
    """
    global _passed, _failed, _skipped
    url = f"{BASE_URL}{endpoint}"
    try:
        fn   = requests.post if method == "POST" else requests.get
        resp = fn(url, headers=HEADERS, json=body, timeout=TIMEOUT)

        ok  = resp.status_code == expect_status
        ico = "✅" if ok else ("⚠️ " if warn_on_fail else "❌")

        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        print(f"[{ico}] {name}")
        print(f"      {method} {endpoint}  →  {resp.status_code}")
        if not ok:
            print(f"      DEBUG: expected {expect_status}, got {resp.status_code}")
            print(f"      DEBUG: response = {_fmt_body(data)}")
            if warn_on_fail:
                _skipped += 1
            else:
                _failed += 1
            return None
        else:
            print(f"      {_fmt_body(data)}")
            _passed += 1
            return data

    except requests.exceptions.ConnectionError as e:
        print(f"[❌] {name}")
        print(f"      {method} {endpoint}")
        print(f"      DEBUG: Connection refused / unreachable")
        print(f"      DEBUG: {e}")
        _failed += 1
        return None

    except requests.exceptions.Timeout:
        print(f"[❌] {name}")
        print(f"      {method} {endpoint}")
        print(f"      DEBUG: Request timed out after {TIMEOUT}s")
        print(f"      DEBUG: Is the instrument physically responding?")
        _failed += 1
        return None

    except Exception as e:
        print(f"[❌] {name}")
        print(f"      {method} {endpoint}")
        print(f"      DEBUG: Unexpected error: {type(e).__name__}: {e}")
        _failed += 1
        return None


# ══════════════════════════════════════════════════════════════════════════════
# TEST GROUPS
# ══════════════════════════════════════════════════════════════════════════════

def test_server():
    section("SERVER / CONNECTIVITY")

    # Health — no instruments needed
    health = test("Server reachable + health", "GET", "/health")
    if health is None:
        print("\n  ⛔ Server unreachable — aborting all tests.")
        print("     Check: Is instrument_server.py running on lab PC?")
        print("     Check: Is Tailscale connected? (tailscale status)")
        print(f"     Check: Can you ping {BASE_URL.split('//')[1].split(':')[0]}?")
        sys.exit(1)

    # OpenAPI — lists all endpoints the server exposes
    section("AVAILABLE ENDPOINTS ON SERVER")
    try:
        r = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        paths = list(r.json()["paths"].keys())
        for p in sorted(paths):
            print(f"      {p}")
    except Exception as e:
        print(f"      DEBUG: Could not fetch endpoint list: {e}")

    # Quick temperature read (no persistent connection)
    test("Quick temperature (no connect needed)", "GET", "/temperature",
         warn_on_fail=True)


def test_eurotherm():
    section("EUROTHERM TEMPERATURE CONTROLLER")

    test("Connect",          "POST", "/eurotherm/connect")
    test("Read temperature", "GET",  "/eurotherm/temperature")

    # Set temperature (safe test — set to current + 0 / a benign value)
    # Uncomment carefully, this will actually move the furnace setpoint:
    # test("Set temperature (25°C)", "POST", "/eurotherm/set_temperature",
    #      body={"temperature": 25.0})

    # Set ramp rate (safe, just configures rate)
    # test("Set ramp rate (5°C/min)", "POST", "/eurotherm/set_ramp_rate",
    #      body={"rate": 5.0})

    test("Disconnect",       "POST", "/eurotherm/disconnect")


def test_daq():
    section("DAQ — Keithley DAQ6510")

    test("Connect",          "POST", "/daq/connect")

    # Write a reset command — should always work if connected
    test("Write *RST",       "POST", "/daq/write",
         body={"command": "*RST"})

    # Query IDN — returns instrument identity string
    idn = test("Query *IDN?", "POST", "/daq/query",
               body={"command": "*IDN?"})
    if idn:
        print(f"      IDN: {idn.get('response', '?')}")

    # Reference temperatures
    test("Reference temperatures", "GET", "/daq/reference_temperatures",
         warn_on_fail=True)

    # Read voltages — the main measurement call
    test("Read voltages (default channels)", "POST", "/daq/read_voltages",
         body={})

    # Read voltages with timestamps
    test("Read voltages + timestamps", "POST", "/daq/read_voltages_with_timestamps",
         body={})

    test("Disconnect", "POST", "/daq/disconnect")


def test_ps():
    section("POWER SUPPLY — Keithley 2230-30-1")

    test("Connect",          "POST", "/ps/connect")

    # Query IDN
    idn = test("Query *IDN?", "POST", "/ps/query",
               body={"command": "*IDN?"})
    if idn:
        print(f"      IDN: {idn.get('response', '?')}")

    # Write *RST — safe reset
    test("Write *RST",       "POST", "/ps/write",
         body={"command": "*RST"})

    # Turn off all outputs — safe
    test("Turn off all channels", "POST", "/ps/turn_off_all")

    # Configure heater — sets limits but doesn't enable
    test("Configure heater CH1 (0A, 0V — safe)", "POST", "/ps/configure_heater",
         body={"channel": 1, "current": 0.0, "voltage": 0.0})

    # Enable heater is commented out — it physically turns on current
    # Uncomment only if instruments are connected and you intend to run:
    # test("Enable heater 1", "POST", "/ps/enable_heater",
    #      body={"heater_num": 1})

    test("Disconnect", "POST", "/ps/disconnect")


def test_error_handling():
    section("ERROR HANDLING")

    # Wrong token → must get 403
    print("[…] Wrong token → expect 403")
    try:
        r = requests.get(f"{BASE_URL}/health",
                         headers={"x-token": "wrong-token"}, timeout=5)
        ok = r.status_code == 403
        print(f"[{'✅' if ok else '❌'}] Wrong token rejected: {r.status_code} "
              f"({'correct' if ok else 'WRONG - server not checking token!'})")
        if ok:
            global _passed
            _passed += 1
        else:
            global _failed
            _failed += 1
    except Exception as e:
        print(f"[❌] DEBUG: {e}")

    # Access without connecting → must get 400
    test("DAQ query without connect → expect 400", "POST", "/daq/query",
         body={"command": "*IDN?"}, expect_status=400)

    test("Eurotherm temp without connect → expect 400", "GET",
         "/eurotherm/temperature", expect_status=400)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

GROUPS = {
    "server":   test_server,
    "eurotherm": test_eurotherm,
    "daq":      test_daq,
    "ps":       test_ps,
    "errors":   test_error_handling,
}

if __name__ == "__main__":
    filter_group = sys.argv[1].lower() if len(sys.argv) > 1 else None

    print(f"\n{'═' * 55}")
    print(f"  Remote Instrument Test")
    print(f"  Server : {BASE_URL}")
    print(f"  Filter : {filter_group or 'all'}")
    print(f"{'═' * 55}")

    t0 = time.time()

    # Always run server check first
    test_server()

    for group, fn in GROUPS.items():
        if group == "server":
            continue   # already ran
        if filter_group is None or filter_group == group:
            fn()

    elapsed = time.time() - t0
    section("SUMMARY")
    print(f"  ✅ Passed  : {_passed}")
    print(f"  ❌ Failed  : {_failed}")
    print(f"  ⚠️  Warned  : {_skipped}")
    print(f"  ⏱  Time    : {elapsed:.1f}s")
    print()

    if _failed > 0:
        print("  Some tests failed — scroll up for DEBUG lines to diagnose.\n")
    else:
        print("  All tests passed! ✅\n")   