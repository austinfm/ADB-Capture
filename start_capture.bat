@echo off
title ADB Capture - Live Sync
python -u -m adb_capture.orchestrator %*
if %ERRORLEVEL% NEQ 0 (
    pause
    exit /b %ERRORLEVEL%
)
