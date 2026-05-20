import os
import sys
import time
import subprocess
import argparse

# Path to the ADB executable installed via the Android CLI plugin
DEFAULT_ADB_PATH = r"C:\Users\afm8\AppData\Local\Android\Sdk\platform-tools\adb.exe"

def find_adb():
    if os.path.exists(DEFAULT_ADB_PATH):
        return DEFAULT_ADB_PATH
    return "adb"

def run_adb_cmd(adb_path, args, timeout=10):
    """Runs an ADB command and returns (stdout, stderr, returncode)."""
    cmd = [adb_path] + args
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.stdout, res.stderr, res.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except Exception as e:
        return "", str(e), -1

def verify_connection(adb_path, ip=None):
    """Verifies that the device is connected and responsive."""
    if ip:
        for attempt in range(3):
            print(f"[Orchestrator] Connection attempt {attempt + 1} to {ip}...")
            run_adb_cmd(adb_path, ["connect", f"{ip}:5555"])
            time.sleep(2)
            stdout, stderr, code = run_adb_cmd(adb_path, ["shell", "getprop", "ro.product.model"])
            if code == 0 and stdout.strip():
                return True, stdout.strip()
            print(f"[Orchestrator] Attempt {attempt + 1} failed: {stderr.strip() or 'Device not responsive'}")
        return False, "Could not establish verified connection to WiFi device."
    else:
        # Check standard connected devices (USB, emulator, etc.)
        stdout, stderr, code = run_adb_cmd(adb_path, ["shell", "getprop", "ro.product.model"])
        if code == 0 and stdout.strip():
            return True, stdout.strip()
        return False, stderr.strip() or "No device connected."

def silent_reconnect(adb_path, ip=None):
    """Attempts to reconnect silently for 30 seconds."""
    start_time = time.time()
    print("[Fail-safe] Connection lost. Attempting silent reconnection for 30 seconds...")
    while time.time() - start_time < 30:
        if ip:
            run_adb_cmd(adb_path, ["connect", f"{ip}:5555"])
        time.sleep(2)
        stdout, stderr, code = run_adb_cmd(adb_path, ["shell", "getprop", "ro.product.model"])
        if code == 0 and stdout.strip():
            print(f"[Fail-safe] Reconnected successfully to device: {stdout.strip()}")
            return True
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser(description="ADB Image Collection Orchestrator")
    parser.add_argument("--ip", type=str, help="IP address of the Android device to connect to via WiFi (e.g. 192.168.1.100)")
    parser.add_argument("--poll-interval", type=int, default=3, help="Polling interval in seconds (default 3)")
    parser.add_argument("--delete-on-device", action="store_true", help="Delete source files from device after successful transfer to prevent bottlenecks")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save pulled images (default: timestamped folder in current directory)")
    parser.add_argument("--post-process", type=str, default=None, help="Path to a Python script to run automatically after the capture session ends")
    args = parser.parse_args()

    adb_path = find_adb()
    print(f"[Orchestrator] Using ADB path: {adb_path}")

    # 1. Verify connection
    print("[Orchestrator] Connecting to device...")
    connected, device_info = verify_connection(adb_path, args.ip)
    if not connected:
        print(f"[Error] Failed to connect to device. Details: {device_info}")
        sys.exit(1)
    
    print(f"[Orchestrator] Connected to: {device_info}")

    # Ensure source path directory exists on the device
    run_adb_cmd(adb_path, ["shell", "mkdir", "-p", "/sdcard/DCIM/Camera"])

    # 2. Establish Temporal Marker
    print("[Orchestrator] Creating experiment marker on device...")
    _, err, code = run_adb_cmd(adb_path, ["shell", "touch", "/sdcard/experiment_marker"])
    if code != 0:
        print(f"[Error] Failed to create experiment marker on device: {err}")
        sys.exit(1)
    print("[Orchestrator] Temporal marker set at /sdcard/experiment_marker")

    # Determine output directory
    if args.output_dir:
        output_path = os.path.abspath(args.output_dir)
        os.makedirs(output_path, exist_ok=True)
        print(f"[Orchestrator] Output directory: {output_path}/")
    else:
        run_id = time.strftime("capture_%Y%m%d_%H%M%S")
        output_path = os.path.abspath(run_id)
        os.makedirs(output_path, exist_ok=True)
        print(f"[Orchestrator] Session folder: {run_id}/")

    # In-memory set to track files pulled this session
    processed_frames = set()

    print("[Orchestrator] System Live: Polling for new images...")

    # 3. Continuous Watch Loop
    try:
        while True:
            # Check for new files using find with -newer flag
            stdout, stderr, code = run_adb_cmd(
                adb_path, 
                ["shell", "find", "/sdcard/DCIM/Camera", "-type", "f", "-newer", "/sdcard/experiment_marker"]
            )

            # If connection dropped, initiate reconnection
            if code != 0:
                # Common connection loss indicator
                if "device not found" in stderr or "offline" in stderr or code == -1 or not stderr:
                    if not silent_reconnect(adb_path, args.ip):
                        print("[CRITICAL ALERT] ADB connection lost. Silently retried for 30s but failed. Operator intervention required.")
                        break
                    continue
                else:
                    # Ignore other find errors (e.g. directory transiently unavailable/empty)
                    time.sleep(args.poll_interval)
                    continue

            # Parse new files
            found_files = [line.strip() for line in stdout.splitlines() if line.strip()]
            
            for remote_file in found_files:
                if remote_file in processed_frames:
                    continue

                filename = os.path.basename(remote_file)
                local_file = os.path.join(output_path, filename)

                print(f"[Orchestrator] New image detected: {remote_file}")
                print(f"[Orchestrator] Pulling: {remote_file} -> {local_file}")
                
                # Pull the file
                _, pull_err, pull_code = run_adb_cmd(adb_path, ["pull", remote_file, local_file])
                
                if pull_code == 0:
                    print(f"[Orchestrator] Pull complete.")
                    processed_frames.add(remote_file)

                    # Prevent device bottlenecking by deleting remote file if requested
                    if args.delete_on_device:
                        print(f"[Orchestrator] Removing file from device to free storage: {remote_file}")
                        run_adb_cmd(adb_path, ["shell", "rm", remote_file])
                else:
                    print(f"[Error] Failed to pull {remote_file}: {pull_err}")

            time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        print("\n[Orchestrator] Monitoring stopped by operator.")
        if args.post_process:
            print(f"[Orchestrator] Running post-process: {args.post_process}")
            subprocess.run([sys.executable, args.post_process])

if __name__ == "__main__":
    main()
