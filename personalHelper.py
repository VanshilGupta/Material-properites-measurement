"""Personal scratch / sanity-check script.

Not imported by the application.  Used for quick experiments — e.g.
verifying that the active Python interpreter sees PySide6, or testing
small numeric snippets pulled out of ``measure_sigma.py``.

Safe to delete if you don't use it.
"""

import PySide6

if __name__ == "__main__":
    print(f"PySide6 module: {PySide6}")
    print(f"PySide6 version: {PySide6.__version__}")
