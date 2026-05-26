# orchestrator.py
import os
import sys
import time
import shlex
from adb_capture import connection
from adb_capture import file_utils


def start_capture(adb_path: str, ip: str | None, args) -> None:
    # Ensure Camera directory exists on device (quote the path to handle potential spaces)
    connection.run_adb_cmd(
        adb_path, ["shell", "mkdir", "-p", shlex.quote(args.device_dir)]
    )

    # 3. Establish temporal marker
    print("[Orchestrator] Creating experiment marker on device...")
    _, err, code = connection.run_adb_cmd(
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
    else:
        run_id = time.strftime("capture_%Y%m%d_%H%M%S")
        output_path = os.path.abspath(os.path.join("captures", run_id))
        os.makedirs(output_path, exist_ok=True)

    print("[Orchestrator] Active Capture Session Flags:")
    print(f"  --device-dir:       {args.device_dir}")
    print(f"  --output-dir:       {output_path}")
    print(f"  --poll-interval:    {args.poll_interval}s")
    print(f"  --type:             {args.type}")
    print(f"  --delete-on-device: {args.delete_on_device}")
    print(f"  --dry-run:          {args.dry_run}")
    if args.serial:
        print(f"  --serial:           {args.serial}")
    if ip:
        print(f"  --ip:               {ip}")
    if args.discover:
        print(f"  --discover:         {args.discover}")

    processed_frames: set = set()
    pending_files: dict = {}  # remote_file -> last_known_size
    if not args.quiet:
        print("[Orchestrator] System Live: Polling for new files...")

    # 4. Continuous watch loop
    try:
        while True:
            stdout, stderr, code = connection.run_adb_cmd(
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
                    if not connection.silent_reconnect(adb_path, ip):
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
                file_type = file_utils.get_file_type_label(filename)

                if args.type != "all" and file_type != args.type:
                    continue

                local_file = os.path.join(output_path, filename)

                current_size = file_utils.get_remote_file_size(adb_path, remote_file)
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
                                _, pull_err, pull_code = connection.run_adb_cmd(
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
                                        connection.run_adb_cmd(
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
