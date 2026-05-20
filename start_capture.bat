@echo off
title ADB Capture - Live Sync
echo ===================================================
echo   ADB IMAGE CAPTURE - LIVE SYNC
echo ===================================================
echo   * Device: Pixel 8
echo   * Connection: WiFi (10.192.168.102)
echo   * Watching: /sdcard/DCIM/Camera
echo   * Saving to: capture_Timestamp\
echo   * Close this window (or press Ctrl+C) to stop.
echo ===================================================
echo.

python -u orchestrator.py --ip 10.192.168.102

echo.
echo Capture stopped.
pause
