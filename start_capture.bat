@echo off
title ADB Capture - Live Sync
setlocal

:: Find where the cached IP is stored
set SCRIPT_DIR=%~dp0
set IP_CACHE_FILE=
if exist "%SCRIPT_DIR%.device_ip" (
    set "IP_CACHE_FILE=%SCRIPT_DIR%.device_ip"
) else if exist .device_ip (
    set "IP_CACHE_FILE=.device_ip"
) else if exist "%USERPROFILE%\.adb_capture_device_ip" (
    set "IP_CACHE_FILE=%USERPROFILE%\.adb_capture_device_ip"
)

if defined IP_CACHE_FILE (
    set /p DEVICE_IP=<%IP_CACHE_FILE%
    echo ===================================================
    echo   ADB IMAGE CAPTURE - LIVE SYNC
    echo ===================================================
    echo   Cached device IP: %DEVICE_IP%
    echo   Starting capture...
    echo ===================================================
    echo.
    python -u -m adb_capture.orchestrator %*
    if %ERRORLEVEL% EQU 0 goto :done

    echo.
    echo [!] Could not connect to %DEVICE_IP%.
    echo     You may be on a different network or the device IP changed.
    echo.
    choice /C YN /M "Attempt auto-discovery via USB?"
    if %ERRORLEVEL% EQU 2 goto :done
    echo.
)

:: ─── Silent USB discovery first ────────────────────────────────────────────
echo Discovering device IP and switching to wireless...
echo.
python -u -m adb_capture.orchestrator --discover %*
if %ERRORLEVEL% EQU 0 goto :done

:: ─── Guided USB discovery (only if silent discovery fails) ────────────────
:discover_walk
echo.
echo ===================================================
echo   WIRELESS SETUP - USB DISCOVERY
echo ===================================================
echo.
echo We'll pair your phone over WiFi using ADB.
echo This takes about 30 seconds the first run.
echo.
echo --- STEP 1: Enable Developer Options (skip if done) ---
echo.
echo   1. Open Settings on your phone
echo   2. Go to  About Phone
echo   3. Tap  Build Number  7 times rapidly
echo      You'll see: "You are now a developer!"
echo.
echo (If you already have Developer Options, skip to Step 2.)
echo.
pause

echo.
echo --- STEP 2: Enable USB Debugging ---
echo.
echo   1. Go to  Settings ^> Developer Options
echo   2. Toggle  USB Debugging  ON
echo.
pause

echo.
echo --- STEP 3: Connect via USB ---
echo.
echo   1. Plug your phone into this computer with a USB cable
echo      (use a data cable, not a charge-only cable)
echo   2. On the phone, tap  ALLOW  when asked about USB Debugging
echo      Tip: check "Always allow from this computer" to skip this next time
echo.
echo Press any key once you see "Allow USB Debugging" on your phone...
pause

echo.
echo Retrying discovery...
echo.
python -u -m adb_capture.orchestrator --discover %*
if %ERRORLEVEL% EQU 0 goto :done

:: ─── Discovery failed: troubleshooting tips ────────────────────────────────
echo.
echo ===================================================
echo   DISCOVERY FAILED - Try these fixes
echo ===================================================
echo.
echo   USB Debugging not enabled
echo   ^> Settings ^> Developer Options ^> USB Debugging = ON
echo.
echo   Phone didn't trust this computer
echo   ^> Unplug and re-plug USB, tap ALLOW on the phone
echo.
echo   Charge-only cable
echo   ^> Switch to a data-capable USB cable
echo.
echo   Phone not on WiFi
echo   ^> Connect the phone to WiFi before running again
echo.
echo   ADB not found
echo   ^> Install Android SDK Platform-Tools and add to PATH
echo     https://developer.android.com/tools/releases/platform-tools
echo.
pause
exit /b 1

:done
echo.
echo Capture stopped.
pause
