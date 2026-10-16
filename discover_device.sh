#!/usr/bin/env bash

# Check for python / python3
# Actually run each candidate: on Windows, python3/python may be Microsoft Store
# stubs that exist on PATH but fail when invoked.
PYTHON_CMD=""
for candidate in python3 python py; do
    if "$candidate" -c "import sys" >/dev/null 2>&1; then
        PYTHON_CMD="$candidate"
        break
    fi
done
if [ -z "$PYTHON_CMD" ]; then
    echo "[!] Python is not installed or not in PATH."
    exit 1
fi

$PYTHON_CMD -u -m adb_capture --discover-only "$@"
