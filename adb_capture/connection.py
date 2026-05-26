import sys
import time
import shutil
import subprocess

# Global target serial to support multi-device environments
device_serial: str | None = None


def find_adb() -> str:
    """Dynamically locates the ADB executable across different OS platforms."""
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        return adb_in_path

    if sys.platform.startswith("win"):
        import os

        windows_default = os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Local",
            "Android",
            "Sdk",
            "platform-tools",
            "adb.exe",
        )
        if os.path.exists(windows_default):
            return windows_default
    elif sys.platform == "darwin":
        import os

        mac_default = os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Android",
            "sdk",
            "platform-tools",
            "adb",
        )
        if os.path.exists(mac_default):
            return mac_default
    else:
        import os

        linux_default = os.path.join(
            os.path.expanduser("~"), "Android", "Sdk", "platform-tools", "adb"
        )
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
