@echo off
title ADB Capture - Discover Device
python -u -m adb_capture.orchestrator --discover-only %*
if %ERRORLEVEL% NEQ 0 (
    pause
    exit /b %ERRORLEVEL%
)
