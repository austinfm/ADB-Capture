#!/usr/bin/env bash

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================${NC}"
echo -e "${BLUE}   ADB IMAGE CAPTURE - LIVE SYNC (macOS/Linux)     ${NC}"
echo -e "${BLUE}===================================================${NC}"

# Check for python / python3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[!] Python is not installed or not in PATH.${NC}"
    exit 1
fi

run_capture() {
    $PYTHON_CMD -u -m adb_capture.orchestrator "$@"
    return $?
}

# --- Try cached IP first ----------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IP_CACHE_FILE=""
if [ -f "$SCRIPT_DIR/.device_ip" ]; then
    IP_CACHE_FILE="$SCRIPT_DIR/.device_ip"
elif [ -f .device_ip ]; then
    IP_CACHE_FILE=".device_ip"
elif [ -f "$HOME/.adb_capture_device_ip" ]; then
    IP_CACHE_FILE="$HOME/.adb_capture_device_ip"
fi

if [ -n "$IP_CACHE_FILE" ]; then
    DEVICE_IP=$(cat "$IP_CACHE_FILE")
    echo -e "Cached device IP: ${GREEN}$DEVICE_IP${NC}"
    echo "Starting capture..."
    echo -e "${BLUE}---------------------------------------------------${NC}"
    
    run_capture "$@"
    ERR_CODE=$?
    
    if [ $ERR_CODE -eq 0 ]; then
        exit 0
    fi
    
    echo ""
    echo -e "${RED}[!] Could not connect to $DEVICE_IP.${NC}"
    echo "You may be on a different network or the device IP changed."
    echo ""
    
    read -p "Attempt auto-discovery via USB? (y/n): " choice
    case "$choice" in 
        [yY][eE][sS]|[yY]) 
            echo ""
            ;;
        *)
            echo "Exiting capture."
            exit 0
            ;;
    esac
fi

# --- Silent USB discovery first ---------------------------------------------
echo "Discovering device IP and switching to wireless..."
echo ""
run_capture --discover "$@"
ERR_CODE=$?

if [ $ERR_CODE -eq 0 ]; then
    exit 0
fi

# --- Guided USB discovery (only if silent discovery fails) ------------------
echo -e "${BLUE}===================================================${NC}"
echo -e "${YELLOW}   WIRELESS SETUP - USB DISCOVERY                  ${NC}"
echo -e "${BLUE}===================================================${NC}"
echo ""
echo "We'll pair your phone over WiFi using ADB."
echo "This takes about 30 seconds the first run."
echo ""
echo -e "${GREEN}--- STEP 1: Enable Developer Options (skip if done) ---${NC}"
echo ""
echo "  1. Open Settings on your phone"
echo "  2. Go to 'About Phone'"
echo "  3. Tap 'Build Number' 7 times rapidly"
echo "     You'll see: 'You are now a developer!'"
echo ""
echo "(If you already have Developer Options, press Enter to skip to Step 2.)"
read -p "Press Enter to continue..."

echo ""
echo -e "${GREEN}--- STEP 2: Enable USB Debugging ---${NC}"
echo ""
echo "  1. Go to Settings > Developer Options"
echo "  2. Toggle 'USB Debugging' ON"
echo ""
read -p "Press Enter to continue..."

echo ""
echo -e "${GREEN}--- STEP 3: Connect via USB ---${NC}"
echo ""
echo "  1. Plug your phone into this computer with a USB cable"
echo "     (use a data cable, not a charge-only cable)"
echo "  2. On the phone, tap ALLOW when asked about USB Debugging"
echo "     Tip: check 'Always allow from this computer' to skip this next time"
echo ""
read -p "Press Enter once you see 'Allow USB Debugging' on your phone..."

echo ""
echo "Retrying discovery..."
echo ""
run_capture --discover "$@"
ERR_CODE=$?

if [ $ERR_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}Capture stopped.${NC}"
    exit 0
fi

# --- Discovery failed: troubleshooting tips ---------------------------------
echo ""
echo -e "${RED}===================================================${NC}"
echo -e "${RED}   DISCOVERY FAILED - Try these fixes              ${NC}"
echo -e "${RED}===================================================${NC}"
echo ""
echo "  USB Debugging not enabled"
echo "  > Settings > Developer Options > USB Debugging = ON"
echo ""
echo "  Phone didn't trust this computer"
echo "  > Unplug and re-plug USB, tap ALLOW on the phone"
echo ""
echo "  Charge-only cable"
echo "  > Switch to a data-capable USB cable"
echo ""
echo "  Phone not on WiFi"
echo "  > Connect the phone to WiFi before running again"
echo ""
echo "  ADB not found"
echo "  > Install Android SDK Platform-Tools and add to PATH"
echo "    https://developer.android.com/tools/releases/platform-tools"
echo ""
exit 1
