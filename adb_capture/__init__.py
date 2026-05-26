"""ADB Capture package.

A utility to continuously sync files from an Android device to a local machine.
"""

from adb_capture.orchestrator import start_capture

__all__ = ["start_capture"]
