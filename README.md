# ADB Capture: Live Sync Utility

A lightweight, robust command-line tool to continuously sync new images, screenshots, and videos from an Android device to a local development machine in real-time. 

Perfect for mobile testing, UX design workflows, collection of training data, or real-time screenshot analysis.

---

## Key Features

- **Automated USB Discovery**: Find your Android device's WiFi IP automatically when connected via USB, configure wireless ADB (`tcpip 5555`), and cache the IP.
- **Wireless Live-Sync**: Once configured, you can unplug the USB cable. The tool polls the device wirelessly over your local WiFi network.
- **Fail-Safe Reconnection**: Automatically monitors connectivity and attempts to reconnect silently for up to 30 seconds if the connection drops.
- **File Stability Protection**: Checks remote file sizes sequentially, ensuring a photo or video is fully written on the device before pulling it (prevents corrupted half-written transfers).
- **Temporal Marker**: Uses an session-based anchor marker (`/sdcard/experiment_marker`) on startup to ensure only images/videos captured *after* starting the utility are pulled.
- **Cross-Platform**: Run on Windows via `.bat` wrapper or macOS/Linux via `.sh` shell script.

---

## Prerequisites

1. **Python 3**: Ensure Python 3 is installed on your computer.
2. **Android SDK Platform-Tools (ADB)**:
   This utility requires the Android Debug Bridge (`adb`) command-line tool.
   - **Check if you have it**: Open a terminal and run `adb version`. If it works, you are good to go.
   - **How to Install**:
     - **macOS**: Install via Homebrew: `brew install android-platform-tools`
     - **Linux (Debian/Ubuntu)**: Install via apt: `sudo apt update && sudo apt install -y adb`
     - **Windows**: Install via Chocolatey `choco install adb` or download the official [SDK Platform-Tools for Windows Zip](https://developer.android.com/tools/releases/platform-tools), extract it, and add the directory containing `adb.exe` to your system environment variables `PATH`.
   - **Auto-Discovery fallback**: If not in your system `PATH`, this tool automatically searches for default SDK paths:
     - **Windows**: `%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe`
     - **macOS**: `~/Library/Android/sdk/platform-tools/adb`
     - **Linux**: `~/Android/Sdk/platform-tools/adb`

---

## Step-by-Step Device Setup

Before running the tool for the first time, configure your Android phone:

1. **Enable Developer Options**:
   - Go to **Settings > About Phone**.
   - Tap **Build Number** 7 times rapidly until a toast message says: *"You are now a developer!"*
2. **Enable USB Debugging**:
   - Go to **Settings > System > Developer Options** (or just search "Developer Options" in Settings).
   - Toggle **USB Debugging** to **ON**.
3. **Connect to WiFi**:
   - Ensure both your computer and your phone are connected to the same local WiFi network.

---

## How to Run

### Option A: Interactive / Guided Setup (Recommended)

Just run the wrapper script for your OS. It will check for a cached IP, launch capture, and walk you through USB pairing if it's the first run:

- **Windows**:
  Double-click `start_capture.bat` or run in terminal:
  ```cmd
  start_capture.bat
  ```
- **macOS / Linux**:
  Make the shell script executable and run:
  ```bash
  chmod +x start_capture.sh
  ./start_capture.sh
  ```

### Option B: Advanced CLI Usage (Direct Python Execution)

You can run the module directly with specific command-line arguments to customize your capture flow:

```bash
python -m adb_capture.orchestrator [FLAGS]
```

*(Note: If you have installed the package via `pip install .`, you can use the global **`adb-capture`** command instead of `python -m adb_capture.orchestrator`)*

#### Available Flags

| Flag | Type | Description |
| :--- | :--- | :--- |
| `--ip <IP>` | String | Manually specify the device's IP (e.g., `192.168.1.100`). Skips automatic USB discovery. |
| `--discover` | Flag | Forces USB discovery to query the device's WiFi IP, configure wireless ADB, and write it to cache. |
| `--poll-interval <SEC>` | Integer | Set how frequently (in seconds) the script checks for new files. Default: `3` seconds. |
| `--delete-on-device` | Flag | Deletes source images/videos from the device after successfully pulling them to save phone storage. |
| `--output-dir <PATH>` | String | Save pulled files to a local computer folder. If omitted, files are saved in a new timestamped folder (`capture_YYYYMMDD_HHMMSS/`). |
| `--device-dir <PATH>` | String | Directory path on the Android device to monitor. Default: `/sdcard/DCIM/Camera`. |
| `--type <TYPE>` | Choice | Restrict capture to specific media types. Options: `all` (default), `image`, `video`. |
| `--dry-run` | Flag | Run in simulation mode: prints what would be pulled or deleted but makes no changes to the device or local filesystem. |
| `--quiet` | Flag | Run in quiet mode: silences periodic polling status and heartbeat logs, printing only transfer operations and errors. |

---

## Example Custom Workflows

### Sync Videos Only
To capture only videos (e.g., MP4 files) and silence periodic heartbeats:
```bash
python -m adb_capture.orchestrator --type video --quiet
```

### Dry Run Sync Preview
To check what files would be copied and deleted from your device without actually transferring them:
```bash
python -m adb_capture.orchestrator --dry-run --delete-on-device
```

### Auto-Delete Captured Files from Phone
If you are doing high-volume capturing and don't want to fill your device's internal storage, enable auto-deletion:
```bash
python -m adb_capture.orchestrator --delete-on-device
```

### Sync Screenshots Instead of Camera Photos
You can direct the sync tool to watch your screenshots directory on your phone instead of the default camera folder:
```bash
# Using Python module
python -m adb_capture.orchestrator --device-dir /sdcard/DCIM/Screenshots

# Or using the start wrapper scripts
start_capture.bat --device-dir /sdcard/DCIM/Screenshots
```

---

## Troubleshooting

- **"No device found" / Connection fails over USB**:
  - Make sure the phone is unlocked and look for a prompt asking: *"Allow USB Debugging?"*. Tap **Allow** (and check "Always allow from this computer" so you don't have to repeat it).
  - Ensure you are using a USB data-capable cable (many charging cables do not transfer data).
- **Connection drops or is unstable**:
  - Keep the phone close to your WiFi router.
  - Some corporate WiFi networks block device-to-device communication (AP Isolation). If this is the case, consider hosting a mobile hotspot from your computer or phone, and connect both devices to that hotspot instead.
- **ADB command not found**:
  - If the script cannot locate `adb`, download Android SDK Platform-Tools manually from [Google's Developer Website](https://developer.android.com/tools/releases/platform-tools) and add the path to your system environment variables.
