@echo off
setlocal
title ADB Capture - Install ADB

where adb >nul 2>&1 && (
    echo [*] adb is already installed:
    adb version
    pause
    exit /b 0
)

where winget >nul 2>&1 || (
    echo [!] winget is not available. Download platform-tools manually:
    echo     https://developer.android.com/tools/releases/platform-tools
    pause
    exit /b 1
)

echo [*] Installing Android SDK Platform-Tools via winget...
winget install --id Google.PlatformTools -e --accept-source-agreements --accept-package-agreements
if %ERRORLEVEL% NEQ 0 (
    echo [!] Installation failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [*] Done. Open a new terminal so the updated PATH takes effect.
pause
