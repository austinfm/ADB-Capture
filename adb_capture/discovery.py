import os
import json
import time
from adb_capture import connection
from adb_capture.ui import prompt_device_selection

DEVICES_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".adb_capture_devices.json",
)
_LEGACY_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".adb_capture_device_ip")


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


def _get_wlan_ip(adb_path: str) -> str | None:
    """Returns the WiFi IP for the currently targeted device by checking common interfaces."""
    interfaces = ["wlan0", "wlan1", "wlan2", "ap0"]
    for iface in interfaces:
        stdout, _, code = connection.run_adb_cmd(
            adb_path, ["shell", "ip", "addr", "show", iface]
        )
        if code == 0:
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith("inet ") and not line.startswith("inet6"):
                    ip = line.split()[1].split("/")[0]
                    if ip and not ip.startswith("127."):
                        return ip

    stdout, _, code = connection.run_adb_cmd(adb_path, ["shell", "ip", "addr"])
    if code == 0:
        current_iface = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line[0].isdigit() or ":" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    current_iface = parts[1].strip().split("@")[0].split()[0]
            if current_iface and ("wlan" in current_iface or "ap" in current_iface):
                if line.startswith("inet ") and not line.startswith("inet6"):
                    ip = line.split()[1].split("/")[0]
                    if ip and not ip.startswith("127."):
                        return ip

    stdout, _, code = connection.run_adb_cmd(adb_path, ["shell", "ip", "route"])
    if code == 0:
        for line in stdout.splitlines():
            if ("wlan" in line or "ap" in line) and "src" in line:
                parts = line.split("src")
                if len(parts) > 1:
                    ip = parts[1].strip().split()[0]
                    if ip and not ip.startswith("127."):
                        return ip
    return None


def discover_device_ip(adb_path: str) -> str | None:
    """Reads WiFi IP(s) from USB-connected device(s). Prompts for selection if multiple are found."""
    print("[Discovery] Checking for USB-connected device...")
    stdout, _, code = connection.run_adb_cmd(adb_path, ["devices"])
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

    original_serial = connection.device_serial
    discovered: list[dict] = []
    for serial in usb_devices:
        connection.device_serial = serial
        ip = _get_wlan_ip(adb_path)
        if ip:
            print(f"[Discovery] Found device {serial} at WiFi IP: {ip}")
            discovered.append({"serial": serial, "ip": ip})

    if not discovered:
        connection.device_serial = original_serial
        print(
            "[Discovery] Could not determine device IP. Is WiFi enabled on the device?"
        )
        return None

    if len(discovered) == 1:
        connection.device_serial = discovered[0]["serial"]
        return discovered[0]["ip"]

    # Multiple USB devices with reachable IPs — let the operator choose
    choices = [{"ip": e["ip"], "model": e["serial"]} for e in discovered]
    selection = prompt_device_selection(choices, label="Discovery")
    if not selection:
        connection.device_serial = original_serial
        print("[Discovery] No device selected.")
        return None

    matched = next(e for e in discovered if e["ip"] == selection["ip"])
    connection.device_serial = matched["serial"]
    return matched["ip"]


def enable_wireless_adb(adb_path: str, ip: str) -> bool:
    """Switches the USB-connected device to TCP mode and connects wirelessly."""
    print("[Discovery] Enabling wireless ADB (tcpip 5555)...")
    _, err, code = connection.run_adb_cmd(adb_path, ["tcpip", "5555"])
    if code != 0:
        print(f"[Discovery] Failed to enable tcpip mode: {err}")
        return False
    time.sleep(2)
    print(f"[Discovery] Connecting wirelessly to {ip}:5555 — you can unplug USB now.")
    connection.run_adb_cmd(adb_path, ["connect", f"{ip}:5555"])
    return True


def resolve_ip(adb_path: str, args) -> str | None:
    """Returns the IP to use, via --ip, --discover, cached selection, or auto-discovery."""
    if args.ip:
        return args.ip

    if args.discover or args.discover_only:
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
    stdout, _, code = connection.run_adb_cmd(adb_path, ["devices"])
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
