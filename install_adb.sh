#!/usr/bin/env bash
# Installs Android SDK Platform-Tools (adb) using the platform's package manager.

if command -v adb >/dev/null 2>&1 && adb version >/dev/null 2>&1; then
    echo "[*] adb is already installed:"
    adb version
    exit 0
fi

echo "[*] Installing Android SDK Platform-Tools..."
case "$(uname -s)" in
    Darwin)
        if ! command -v brew >/dev/null 2>&1; then
            echo "[!] Homebrew not found. Install it from https://brew.sh first."
            exit 1
        fi
        brew install --cask android-platform-tools
        ;;
    Linux)
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update && sudo apt-get install -y adb
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y android-tools
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -S --noconfirm android-tools
        else
            echo "[!] Unsupported package manager. Download platform-tools manually:"
            echo "    https://developer.android.com/tools/releases/platform-tools"
            exit 1
        fi
        ;;
    MINGW*|MSYS*|CYGWIN*)
        winget.exe install --id Google.PlatformTools -e --accept-source-agreements --accept-package-agreements
        echo "[*] Open a new terminal so the updated PATH takes effect."
        ;;
    *)
        echo "[!] Unsupported OS. Download platform-tools manually:"
        echo "    https://developer.android.com/tools/releases/platform-tools"
        exit 1
        ;;
esac
