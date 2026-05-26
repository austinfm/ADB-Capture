import argparse
import sys
import os
from adb_capture import connection
from adb_capture import discovery
from adb_capture import orchestrator
from adb_capture import ui


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
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the cached device IP address(es) and disconnect wireless ADB connections, then exit",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Force USB discovery: reads WiFi IP from USB-connected device, enables wireless ADB, then exits",
    )
    args = parser.parse_args()

    adb_path = connection.find_adb()
    print(f"[Orchestrator] Using ADB: {adb_path}")

    if args.health_check:
        sys.exit(connection.health_check(adb_path))

    if args.clear_cache:
        if os.path.exists(discovery.DEVICES_CACHE_FILE):
            try:
                os.remove(discovery.DEVICES_CACHE_FILE)
                print(f"[Cache] Cleared IP cache ({discovery.DEVICES_CACHE_FILE}).")
            except Exception as e:
                print(f"[Cache] Failed to delete cache file: {e}")
        else:
            print("[Cache] No cache file found. Nothing to clear.")
        print("[Cache] Disconnecting active wireless ADB connections...")
        connection.run_adb_cmd(adb_path, ["disconnect"])
        sys.exit(0)

    # 1. Resolve device IP / Serial
    if args.serial:
        connection.device_serial = args.serial
        ip = None
    else:
        ip = discovery.resolve_ip(adb_path, args)

    if args.discover_only and not ip:
        print("[Error] Discovery failed: Could not determine device IP. Please ensure your device is connected via USB, has WiFi enabled, and is on the same network.")
        sys.exit(1)

    # 2. Verify connection
    connected = False
    device_info = ""

    if args.serial:
        connected, device_info = connection.verify_connection(adb_path, None)
    elif ip:
        connected, device_info = connection.verify_connection(adb_path, ip)
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
                discovered_ip = discovery.discover_device_ip(adb_path)
                if discovered_ip and discovery.enable_wireless_adb(adb_path, discovered_ip):
                    discovery.save_device_to_cache(discovered_ip)
                    ip = discovered_ip
                    connected, device_info = connection.verify_connection(adb_path, ip)
            else:
                print("Exiting.")
                sys.exit(1)
    else:
        connected, device_info = connection.verify_connection(adb_path, None)

    if not connected:
        if args.serial:
            print(
                f"[Error] Failed to connect: Specified device '{args.serial}' is offline or not found."
            )
            sys.exit(1)

        ui.show_onboarding_guide()
        print("[Discovery] Retrying discovery...")
        discovered_ip = discovery.discover_device_ip(adb_path)
        if discovered_ip and discovery.enable_wireless_adb(adb_path, discovered_ip):
            discovery.save_device_to_cache(discovered_ip)
            ip = discovered_ip
            connected, device_info = connection.verify_connection(adb_path, ip)

    if not connected:
        print("[Error] Failed to connect: Could not establish verified connection.")
        sys.exit(1)

    print(f"[Orchestrator] Connected to: {device_info}")
    if ip:
        discovery.save_device_to_cache(ip, device_info)
        print(f"[Orchestrator] Device IP: {ip} (saved to cache)")

    if args.discover_only:
        print("[Discovery] Wireless setup complete. Device is cached and ready.")
        sys.exit(0)

    # 3. Start core watch loop
    orchestrator.start_capture(adb_path, ip, args)


if __name__ == "__main__":
    main()
