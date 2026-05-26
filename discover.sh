#!/usr/bin/env bash

# Check for python / python3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[!] Python is not installed or not in PATH."
    exit 1
fi

$PYTHON_CMD -u -m adb_capture.orchestrator --discover "$@"
