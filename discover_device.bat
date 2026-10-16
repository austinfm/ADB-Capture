@echo off
setlocal
title ADB Capture - Discover Device

rem Actually run each candidate: python/python3 may be Microsoft Store stubs
rem that exist on PATH but fail when invoked.
set "PYTHON_CMD="
for %%P in (python py python3) do (
    if not defined PYTHON_CMD (
        %%P -c "import sys" >nul 2>&1 && set "PYTHON_CMD=%%P"
    )
)
rem Fall back to common install locations not on PATH (e.g. conda without init).
for %%P in (
    "%LOCALAPPDATA%\miniconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%LOCALAPPDATA%\anaconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%ProgramData%\miniconda3\python.exe"
    "%ProgramData%\anaconda3\python.exe"
) do (
    if not defined PYTHON_CMD if exist %%P set "PYTHON_CMD=%%~P"
)
if not defined PYTHON_CMD (
    echo [!] Python is not installed or not in PATH.
    pause
    exit /b 1
)

"%PYTHON_CMD%" -u -m adb_capture --discover-only %*
if %ERRORLEVEL% NEQ 0 (
    pause
    exit /b %ERRORLEVEL%
)
