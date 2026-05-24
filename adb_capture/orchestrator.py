import os
import sys
import time
import json
import subprocess
import argparse
import shutil
import shlex

DEVICES_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".adb_capture_devices.json")
_LEGACY_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".adb_capture_device_ip")

# Global target serial to support multi-device environments
device_serial: str | None = None


def find_adb() -> str:
    """Dynamically locates the ADB executable across different OS platforms."""
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        return adb_in_path

    home = os.path.expanduser("~")

    if sys.platform.startswith("win"):
        windows_default = os.path.join(
            home, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"
        )
        if os.path.exists(windows_default):
            return windows_default
    elif sys.platform == "darwin":
        mac_default = os.path.join(
            home, "Library", "Android", "sdk", "platform-tools", "adb"
        )
        if os.path.exists(mac_default):
            return mac_default
    else:
        linux_default = os.path.join(home, "Android", "Sdk", "platform-tools", "adb")
        if os.path.exists(linux_default):
            return linux_default

    return "adb"


def run_adb_cmd(adb_path: str, args: list, timeout: int = 10) -> tuple[str, str, int]:
    """Runs an ADB command and returns (stdout, stderr, returncode)."""
    global device_serial
    cmd_args = args
    if (
        device_serial
        and args
        and args[0]
        not in (
            "devices",
            "connect",
            "disconnect",
            "version",
            "start-server",
            "kill-server",
        )
    ):
        cmd_args = ["-s", device_serial] + args

    cmd = [adb_path] + cmd_args
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.stdout, res.stderr, res.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except Exception as e:
        return "", str(e), -1


def load_cached_devices() -> list[dict]:
    """Returns the list of cached devices, migrating from the legacy single-IP file if needed."""
    if not os.path.exists(DEVICES_CACHE_FILE) and os.path.exists(_LEGACY_CACHE_FILE):
        try:
            with open(_LEGACY_CACHE_FILE) as f:
                ip = f.read().strip()
            if ip:
                _write_devices_cache([{"ip": ip, "model": ""}])
            os.remove(_LEGACY_CACHE_FILE)
        except Exception:
            pass

    if not os.path.exists(DEVICES_CACHE_FILE):
        return []
    try:
        with open(DEVICES_CACHE_FILE) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _write_devices_cache(devices: list[dict]) -> None:
    try:
        with open(DEVICES_CACHE_FILE, "w") as f:
            json.dump(devices, f, indent=2)
    except Exception:
        pass


def save_device_to_cache(ip: str, model: str = "") -> None:
    """Upserts a device entry into the multi-device cache, keyed by IP."""
    devices = load_cached_devices()
    for d in devices:
        if d["ip"] == ip:
            if model:
                d["model"] = model
            _write_devices_cache(devices)
            return
    devices.append({"ip": ip, "model": model})
    _write_devices_cache(devices)


def prompt_device_selection(
    devices: list[dict], label: str = "Select device"
) -> dict | None:
    """Displays a numbered device menu and returns the user's selection."""
    print(f"\n[{label}] Multiple devices available:")
    for i, d in enumerate(devices, 1):
        entry = f"  {i}. {d['ip']}"
        if d.get("model"):
            entry += f"  ({d['model']})"
        print(entry)
    print()
    try:
        raw = input(f"Enter number (1-{len(devices)}): ").strip()
        idx = int(raw) - 1
        if 0 <= idx < len(devices):
            return devices[idx]
    except (ValueError, KeyboardInterrupt):
        pass
    return None


def _get_wlan0_ip(adb_path: str) -> str | None:
    """Returns the wlan0 IP for the currently targeted device."""
    stdout, _, code = run_adb_cmd(adb_path, ["shell", "ip", "addr", "show", "wlan0"])
    if code == 0:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("inet ") and not line.startswith("inet6"):
                return line.split()[1].split("/")[0]

    stdout, _, code = run_adb_cmd(adb_path, ["shell", "ip", "route"])
    if code == 0:
        for line in stdout.splitlines():
            if "wlan0" in line and "src" in line:
                parts = line.split("src")
                if len(parts) > 1:
                    return parts[1].strip().split()[0]
    return None


def get_remote_file_size(adb_path: str, remote_file: str) -> int | None:
    """Retrieves the file size of the remote file in bytes using stat -c %s with ls -l fallback."""
    quoted_file = shlex.quote(remote_file)
    stdout, _, code = run_adb_cmd(adb_path, ["shell", "stat", "-c", "%s", quoted_file])
    if code == 0:
        try:
            return int(stdout.strip())
        except ValueError:
            pass

    stdout, _, code = run_adb_cmd(adb_path, ["shell", "ls", "-l", quoted_file])
    if code == 0:
        parts = stdout.strip().split()
        for part in parts[3:6]:
            if part.isdigit():
                return int(part)
    return None


def get_file_type_label(filename: str) -> str:
    """Returns a label ('image', 'video', or 'file') based on extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif"):
        return "image"
    elif ext in (".mp4", ".mkv", ".3gp", ".webm", ".mov", ".avi"):
        return "video"
    return "file"


def discover_device_ip(adb_path: str) -> str | None:
    """Reads WiFi IP(s) from USB-connected device(s). Prompts for selection if multiple are found."""
    global device_serial
    print("[Discovery] Checking for USB-connected device...")
    stdout, _, code = run_adb_cmd(adb_path, ["devices"])
    lines = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip() and "List of" not in line
    ]
    usb_devices = [
        line.split()[0]
        for line in lines
        if "\tdevice" in line and ":" not in line.split()[0]
    ]
    if code != 0 or not usb_devices:
        print(
            "[Discovery] No USB device found. Connect the device via USB with USB debugging enabled."
        )
        return None

    original_serial = device_serial
    discovered: list[dict] = []
    for serial in usb_devices:
        device_serial = serial
        ip = _get_wlan0_ip(adb_path)
        if ip:
            print(f"[Discovery] Found device {serial} at WiFi IP: {ip}")
            discovered.append({"serial": serial, "ip": ip})

    if not discovered:
        device_serial = original_serial
        print(
            "[Discovery] Could not determine device IP. Is WiFi enabled on the device?"
        )
        return None

    if len(discovered) == 1:
        device_serial = discovered[0]["serial"]
        return discovered[0]["ip"]

    # Multiple USB devices with reachable IPs — let the operator choose
    choices = [{"ip": e["ip"], "model": e["serial"]} for e in discovered]
    selection = prompt_device_selection(choices, label="Discovery")
    if not selection:
        device_serial = original_serial
        print("[Discovery] No device selected.")
        return None

    matched = next(e for e in discovered if e["ip"] == selection["ip"])
    device_serial = matched["serial"]
    return matched["ip"]


def enable_wireless_adb(adb_path: str, ip: str) -> bool:
    """Switches the USB-connected device to TCP mode and connects wirelessly."""
    print("[Discovery] Enabling wireless ADB (tcpip 5555)...")
    _, err, code = run_adb_cmd(adb_path, ["tcpip", "5555"])
    if code != 0:
        print(f"[Discovery] Failed to enable tcpip mode: {err}")
        return False
    time.sleep(2)
    print(f"[Discovery] Connecting wirelessly to {ip}:5555 — you can unplug USB now.")
    run_adb_cmd(adb_path, ["connect", f"{ip}:5555"])
    return True


def resolve_ip(adb_path: str, args) -> str | None:
    """Returns the IP to use, via --ip, --discover, cached selection, or auto-discovery."""
    if args.ip:
        return args.ip

    if args.discover:
        ip = discover_device_ip(adb_path)
        if not ip:
            return None
        enable_wireless_adb(adb_path, ip)
        save_device_to_cache(ip)
        return ip

    # No flag — consult cache
    cached = load_cached_devices()
    if len(cached) == 1:
        print(f"[Orchestrator] Using cached device IP: {cached[0]['ip']}")
        return cached[0]["ip"]
    elif len(cached) > 1:
        selection = prompt_device_selection(cached, label="Orchestrator")
        if not selection:
            return None
        print(f"[Orchestrator] Selected device: {selection['ip']}")
        return selection["ip"]

    # Check for already-active ADB connections
    stdout, _, code = run_adb_cmd(adb_path, ["devices"])
    if code == 0:
        lines = [
            line.strip()
            for line in stdout.splitlines()
            if line.strip() and "List of" not in line
        ]
        active = [line.split()[0] for line in lines if "\tdevice" in line]
        wireless = [d for d in active if ":" in d]

        if len(wireless) == 1:
            ip_part = wireless[0].split(":")[0]
            print(
                f"[Orchestrator] Found active wireless device connection: {wireless[0]}"
            )
            save_device_to_cache(ip_part)
            return ip_part
        elif len(wireless) > 1:
            choices = [{"ip": d.split(":")[0], "model": d} for d in wireless]
            selection = prompt_device_selection(choices, label="Orchestrator")
            if selection:
                save_device_to_cache(selection["ip"])
                return selection["ip"]
            return None
        elif active:
            print(f"[Orchestrator] Found active USB device connection: {active[0]}")
            return None

    print(
        "[Orchestrator] No IP provided, no cache found, and no active device detected. Attempting USB discovery..."
    )
    ip = discover_device_ip(adb_path)
    if ip:
        enable_wireless_adb(adb_path, ip)
        save_device_to_cache(ip)
        return ip
    return None


def verify_connection(adb_path: str, ip: str | None = None) -> tuple[bool, str]:
    """Verifies that the device is connected and responsive."""
    global device_serial
    if ip:
        target = f"{ip}:5555"
        for attempt in range(3):
            print(f"[Orchestrator] Connection attempt {attempt + 1} to {ip}...")
            run_adb_cmd(adb_path, ["connect", target])
            time.sleep(2)

            old_serial = device_serial
            device_serial = target
            stdout, stderr, code = run_adb_cmd(
                adb_path, ["shell", "getprop", "ro.product.model"]
            )
            if code == 0 and stdout.strip():
                return True, stdout.strip()
            device_serial = old_serial
            print(
                f"[Orchestrator] Attempt {attempt + 1} failed: {stderr.strip() or 'Device not responsive'}"
            )
        return False, "Could not establish verified connection to WiFi device."
    else:
        stdout, _, code = run_adb_cmd(adb_path, ["devices"])
        if code == 0:
            lines = [
                line.strip()
                for line in stdout.splitlines()
                if line.strip() and "List of" not in line
            ]
            devices = [line.split()[0] for line in lines if "\tdevice" in line]
            if devices:
                old_serial = device_serial
                if not device_serial:
                    device_serial = devices[0]
                elif device_serial not in devices:
                    return (
                        False,
                        f"Device with serial '{device_serial}' is not connected.",
                    )

                stdout, stderr, code = run_adb_cmd(
                    adb_path, ["shell", "getprop", "ro.product.model"]
                )
                if code == 0 and stdout.strip():
                    return True, stdout.strip()
                device_serial = old_serial
        return False, "No device connected or specified device not found."


def silent_reconnect(adb_path: str, ip: str | None = None) -> bool:
    """Attempts to reconnect silently for 30 seconds."""
    start_time = time.time()
    print(
        "[Fail-safe] Connection lost. Attempting silent reconnection for 30 seconds..."
    )
    while time.time() - start_time < 30:
        if ip:
            run_adb_cmd(adb_path, ["connect", f"{ip}:5555"])
        time.sleep(2)
        stdout, _, code = run_adb_cmd(
            adb_path, ["shell", "getprop", "ro.product.model"]
        )
        if code == 0 and stdout.strip():
            print(f"[Fail-safe] Reconnected successfully to device: {stdout.strip()}")
            return True
        time.sleep(1)
    return False


def health_check(adb_path: str) -> int:
    """Verifies ADB is available and reports connected devices. Returns 0 on success, 1 on failure."""
    print("[Health] Checking ADB binary...")
    stdout, stderr, code = run_adb_cmd(adb_path, ["version"])
    if code != 0:
        print(f"[Health] FAIL: ADB not functional: {stderr.strip()}")
        return 1
    version_line = stdout.splitlines()[0] if stdout.splitlines() else "unknown"
    print(f"[Health] OK: {version_line}")

    print("[Health] Checking connected devices...")
    stdout, stderr, code = run_adb_cmd(adb_path, ["devices"])
    if code != 0:
        print(f"[Health] FAIL: Could not list devices: {stderr.strip()}")
        return 1

    lines = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip() and "List of" not in line
    ]
    devices = [line for line in lines if "\tdevice" in line]
    unauthorized = [line for line in lines if "unauthorized" in line]
    offline = [line for line in lines if "offline" in line]

    if devices:
        print(f"[Health] OK: {len(devices)} device(s) connected:")
        for d in devices:
            print(f"  {d}")
    else:
        print("[Health] INFO: No authorized devices connected.")

    if unauthorized:
        print(
            "[Health] WARN: Unauthorized device(s) — accept the USB debugging prompt on the device:"
        )
        for d in unauthorized:
            print(f"  {d}")

    if offline:
        print("[Health] WARN: Offline device(s) — try unplugging and reconnecting:")
        for d in offline:
            print(f"  {d}")

    if not devices and not unauthorized and not offline:
        print(
            "[Health] No devices detected at all — connect a device via USB or run --discover."
        )
        return 1

    print("[Health] Health check complete.")
    return 0


def show_onboarding_guide():
    """Displays step-by-step instructions to set up USB debugging and pairing."""
    print("\n" + "=" * 55)
    print("  WIRELESS SETUP - USB DISCOVERY")
    print("=" * 55 + "\n")
    print("We'll pair your phone over WiFi using ADB.")
    print("This takes about 30 seconds on the first run.\n")

    print("--- STEP 1: Enable Developer Options (skip if done) ---")
    print("  1. Open Settings on your phone")
    print("  2. Go to 'About Phone'")
    print("  3. Tap 'Build Number' 7 times rapidly")
    print("     You'll see: 'You are now a developer!'\n")
    print("(If you already have Developer Options, press Enter to continue to Step 2.)")
    try:
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)

    print("\n--- STEP 2: Enable USB Debugging ---")
    print("  1. Go to Settings > Developer Options")
    print("  2. Toggle 'USB Debugging' to ON\n")
    try:
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)

    print("\n--- STEP 3: Connect via USB ---")
    print("  1. Plug your phone into this computer with a USB cable")
    print("     (use a data cable, not a charge-only cable)")
    print("  2. On the phone, tap ALLOW when asked about USB Debugging")
    print("     Tip: check 'Always allow from this computer' to skip this next time\n")
    try:
        input("Press Enter once you see 'Allow USB Debugging' on your phone...")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
    print()


def main():
    parser = argparse.ArgumentParser(description="ADB Image Collection Orchestrator")
    parser.add_argument(
        "--serial",
        type=str,
        help="Target a specific device by its ADB serial number (USB or wireless). Skips discovery.",
    )
    parser.add_argument(
        "--ip",
        type=str,
        help="IP address of the Android device (e.g. 192.168.1.100). Skips discovery.",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Force USB discovery: reads WiFi IP from USB-connected device, enables wireless ADB, then proceeds.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=3,
        help="Polling interval in seconds (default 3)",
    )
    parser.add_argument(
        "--delete-on-device",
        action="store_true",
        help="Delete source files from device after transfer to prevent storage bottlenecks",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save pulled images (default: timestamped folder)",
    )
    parser.add_argument(
        "--device-dir",
        type=str,
        default="/sdcard/DCIM/Camera",
        help="Directory on the Android device to monitor (default: /sdcard/DCIM/Camera)",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["all", "image", "video"],
        default="all",
        help="Media type to capture (all, image, video. default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the sync process without modifying the device or pulling files",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Silence polling, heartbeat, and write-progress messages",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Verify ADB is available and list connected devices, then exit",
    )
    args = parser.parse_args()

    adb_path = find_adb()
    print(f"[Orchestrator] Using ADB: {adb_path}")

    if args.health_check:
        sys.exit(health_check(adb_path))

    # 1. Resolve device IP / Serial
    if args.serial:
        global device_serial
        device_serial = args.serial
        ip = None
    else:
        ip = resolve_ip(adb_path, args)

    # 2. Verify connection
    connected = False
    device_info = ""

    if args.serial:
        connected, device_info = verify_connection(adb_path, None)
    elif ip:
        connected, device_info = verify_connection(adb_path, ip)
        if not connected:
            print(f"\n[!] Could not connect to {ip}.")
            print("You may be on a different network or the device IP changed.\n")
            try:
                choice = (
                    input("Attempt auto-discovery via USB? (y/n): ").strip().lower()
                )
            except KeyboardInterrupt:
                sys.exit(0)
            if choice in ("y", "yes"):
                print("[Discovery] Discovering device IP and switching to wireless...")
                discovered_ip = discover_device_ip(adb_path)
                if discovered_ip and enable_wireless_adb(adb_path, discovered_ip):
                    save_device_to_cache(discovered_ip)
                    ip = discovered_ip
                    connected, device_info = verify_connection(adb_path, ip)
            else:
                print("Exiting.")
                sys.exit(1)
    else:
        connected, device_info = verify_connection(adb_path, None)

    if not connected:
        if args.serial:
            print(
                f"[Error] Failed to connect: Specified device '{args.serial}' is offline or not found."
            )
            sys.exit(1)

        show_onboarding_guide()
        print("[Discovery] Retrying discovery...")
        discovered_ip = discover_device_ip(adb_path)
        if discovered_ip and enable_wireless_adb(adb_path, discovered_ip):
            save_device_to_cache(discovered_ip)
            ip = discovered_ip
            connected, device_info = verify_connection(adb_path, ip)

    if not connected:
        print("[Error] Failed to connect: Could not establish verified connection.")
        sys.exit(1)

    print(f"[Orchestrator] Connected to: {device_info}")
    if ip:
        save_device_to_cache(ip, device_info)
        print(f"[Orchestrator] Device IP: {ip} (saved to cache)")

    # Ensure Camera directory exists on device (quote the path to handle potential spaces)
    run_adb_cmd(adb_path, ["shell", "mkdir", "-p", shlex.quote(args.device_dir)])

    # 3. Establish temporal marker
    print("[Orchestrator] Creating experiment marker on device...")
    _, err, code = run_adb_cmd(
        adb_path, ["shell", "touch", "/sdcard/experiment_marker"]
    )
    if code != 0:
        print(f"[Error] Failed to create experiment marker: {err}")
        sys.exit(1)
    print("[Orchestrator] Temporal marker set at /sdcard/experiment_marker")

    # Determine output directory
    if args.output_dir:
        output_path = os.path.abspath(args.output_dir)
        os.makedirs(output_path, exist_ok=True)
        print(f"[Orchestrator] Output directory: {output_path}/")
    else:
        run_id = time.strftime("capture_%Y%m%d_%H%M%S")
        output_path = os.path.abspath(os.path.join("captures", run_id))
        os.makedirs(output_path, exist_ok=True)
        print(f"[Orchestrator] Session folder: captures/{run_id}/")

    processed_frames: set = set()
    pending_files: dict = {}  # remote_file -> last_known_size
    if not args.quiet:
        print("[Orchestrator] System Live: Polling for new files...")

    # 4. Continuous watch loop
    try:
        while True:
            stdout, stderr, code = run_adb_cmd(
                adb_path,
                [
                    "shell",
                    "find",
                    shlex.quote(args.device_dir),
                    "-type",
                    "f",
                    "-newer",
                    "/sdcard/experiment_marker",
                ],
            )

            if code != 0:
                if (
                    "device not found" in stderr
                    or "offline" in stderr
                    or code == -1
                    or not stderr
                ):
                    if not silent_reconnect(adb_path, ip):
                        print(
                            "[CRITICAL ALERT] ADB connection lost. Silently retried for 30s but failed. Operator intervention required."
                        )
                        break
                    continue
                else:
                    time.sleep(args.poll_interval)
                    continue

            found_files = [line.strip() for line in stdout.splitlines() if line.strip()]

            for pending_file in list(pending_files.keys()):
                if pending_file not in found_files:
                    del pending_files[pending_file]

            for remote_file in found_files:
                if remote_file in processed_frames:
                    continue

                filename = os.path.basename(remote_file)
                file_type = get_file_type_label(filename)

                if args.type != "all" and file_type != args.type:
                    continue

                local_file = os.path.join(output_path, filename)

                current_size = get_remote_file_size(adb_path, remote_file)
                if current_size is None:
                    continue

                if remote_file not in pending_files:
                    pending_files[remote_file] = current_size
                    if not args.quiet:
                        print(
                            f"[Orchestrator] New {file_type} detected: {remote_file} (waiting for file to write completely)"
                        )
                else:
                    last_size = pending_files[remote_file]
                    if current_size == last_size:
                        if current_size > 0:
                            if args.dry_run:
                                print(
                                    f"[Dry Run] Would pull {file_type}: {remote_file} -> {local_file}"
                                )
                                processed_frames.add(remote_file)
                                del pending_files[remote_file]
                                if args.delete_on_device:
                                    print(
                                        f"[Dry Run] Would remove from device: {remote_file}"
                                    )
                            else:
                                print(
                                    f"[Orchestrator] Pulling {file_type}: {remote_file} -> {local_file}"
                                )
                                _, pull_err, pull_code = run_adb_cmd(
                                    adb_path, ["pull", remote_file, local_file]
                                )

                                if pull_code == 0:
                                    print("[Orchestrator] Pull complete.")
                                    processed_frames.add(remote_file)
                                    del pending_files[remote_file]
                                    if args.delete_on_device:
                                        print(
                                            f"[Orchestrator] Removing from device: {remote_file}"
                                        )
                                        run_adb_cmd(
                                            adb_path,
                                            ["shell", "rm", shlex.quote(remote_file)],
                                        )
                                else:
                                    print(
                                        f"[Error] Failed to pull {remote_file}: {pull_err}"
                                    )
                    else:
                        if not args.quiet:
                            print(
                                f"[Orchestrator] {file_type} is still writing (size: {current_size} bytes)..."
                            )
                        pending_files[remote_file] = current_size

            time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        print("\n[Orchestrator] Monitoring stopped by operator.")


if __name__ == "__main__":
    main()
