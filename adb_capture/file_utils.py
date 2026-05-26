import os
import shlex
from adb_capture.connection import run_adb_cmd


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
