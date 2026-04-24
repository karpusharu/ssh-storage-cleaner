#!/usr/bin/env python3
"""
SSH Storage Cleaner - Delete old camera recordings from Hetzner Storage Box
Loads config from .env file — never hardcode credentials.
"""

import subprocess
import datetime
import sys
import os
import logging
from typing import Tuple, List
from dotenv import load_dotenv

load_dotenv()

# ── Config from .env ──────────────────────────────────────────────────────────
SSH_HOST       = os.getenv("SSH_HOST", "")
SSH_PORT       = os.getenv("SSH_PORT", "23")
SSH_USER       = os.getenv("SSH_USER", "")
SSH_PASS       = os.getenv("SSH_PASS", "")          # used only if no SSH key
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "14"))
BASE_DIR       = os.getenv("BASE_DIR", "")
DRY_RUN        = os.getenv("DRY_RUN", "false").lower() == "true"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(__file__), "cleanup.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── SSH helpers ───────────────────────────────────────────────────────────────

def _build_ssh_cmd(command: str) -> list:
    """Build the ssh command list, using sshpass if a password is set."""
    base = []
    if SSH_PASS:
        base = ["sshpass", "-p", SSH_PASS]
    base += [
        "ssh",
        "-p", SSH_PORT,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
    ]
    if not SSH_PASS:
        base += ["-o", "BatchMode=yes"]   # key-only: never prompt
    base += [f"{SSH_USER}@{SSH_HOST}", command]
    return base


def ssh_run(command: str, timeout: int = 600) -> Tuple[int, str, str]:
    """Run a command on the remote server via SSH."""
    try:
        result = subprocess.run(
            _build_ssh_cmd(command),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError as e:
        return -1, "", f"Binary not found: {e}"
    except Exception as e:
        return -1, "", str(e)


# ── Connection ────────────────────────────────────────────────────────────────

def test_connection() -> bool:
    log.info("Testing SSH connection to %s:%s …", SSH_HOST, SSH_PORT)
    code, out, err = ssh_run("pwd && df -h .")
    if code != 0:
        log.error("Connection failed: %s", err)
        log.error("Tip: ssh -p %s %s@%s", SSH_PORT, SSH_USER, SSH_HOST)
        return False
    log.info("Connected. Server output:\n%s", out)
    return True


# ── Folder discovery ──────────────────────────────────────────────────────────

def list_day_folders() -> List[str]:
    """
    List all YYYY/MM/DD folders using ls (compatible with Hetzner Storage Box
    restricted shell which does not support `find`).
    """
    base = BASE_DIR if BASE_DIR else "."
    log.info("Scanning %s for date folders …", base)

    folders = []

    # List years
    code, out, _ = ssh_run(f"ls {base}")
    if code != 0:
        return []

    for year in out.splitlines():
        year = year.strip()
        if not year.isdigit() or len(year) != 4:
            continue
        # List months
        code, out2, _ = ssh_run(f"ls {base}/{year}")
        if code != 0:
            continue
        for month in out2.splitlines():
            month = month.strip()
            if not month.isdigit() or len(month) != 2:
                continue
            # List days
            code, out3, _ = ssh_run(f"ls {base}/{year}/{month}")
            if code != 0:
                continue
            for day in out3.splitlines():
                day = day.strip()
                if not day.isdigit() or len(day) != 2:
                    continue
                path = f"{year}/{month}/{day}" if base == "." else f"{base}/{year}/{month}/{day}"
                folders.append(path)

    log.info("Found %d day folders", len(folders))
    return folders


# ── Date logic ────────────────────────────────────────────────────────────────

def parse_folder_date(path: str) -> datetime.date:
    """Parse date from path ending in YYYY/MM/DD."""
    parts = path.rstrip("/").split("/")
    year, month, day = int(parts[-3]), int(parts[-2]), int(parts[-1])
    return datetime.date(year, month, day)


def is_expired(path: str) -> bool:
    try:
        cutoff = datetime.date.today() - datetime.timedelta(days=RETENTION_DAYS)
        return parse_folder_date(path) < cutoff
    except Exception:
        return False


def categorize(folders: List[str]) -> Tuple[List[str], List[str]]:
    keep, delete = [], []
    for f in folders:
        (delete if is_expired(f) else keep).append(f)
    return keep, delete


# ── Deletion ──────────────────────────────────────────────────────────────────

def delete_folder(path: str) -> bool:
    if DRY_RUN:
        log.info("  [DRY RUN] would delete: %s", path)
        return True
    code, _, err = ssh_run(f"rm -rf '{path}'")
    if code != 0:
        log.error("  Failed to delete %s: %s", path, err)
    return code == 0


def delete_folders(folders: List[str]) -> int:
    if not folders:
        return 0
    mode = "[DRY RUN] " if DRY_RUN else ""
    log.info("%sDeleting %d old folder(s) …", mode, len(folders))
    count = 0
    for f in folders:
        log.info("  → %s", f)
        if delete_folder(f):
            count += 1
    return count


def remove_empty_parents():
    """Clean up empty year/month directories left after deletion."""
    if DRY_RUN:
        return
    base = BASE_DIR if BASE_DIR else "."
    ssh_run(f"find {base} -mindepth 1 -maxdepth 2 -type d -empty -delete 2>/dev/null")
    log.info("Empty parent folders removed")


# ── Reporting ─────────────────────────────────────────────────────────────────

def show_summary(kept: List[str], deleted: int):
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("  Retention   : %d days", RETENTION_DAYS)
    log.info("  Dry run     : %s", DRY_RUN)
    log.info("  Kept        : %d folder(s)", len(kept))
    log.info("  Deleted     : %d folder(s)", deleted)
    if kept:
        log.info("  Oldest kept : %s", kept[0].split("/")[-3:])
        log.info("  Newest kept : %s", kept[-1].split("/")[-3:])
    log.info("=" * 60)


def confirm(count: int) -> bool:
    if DRY_RUN:
        log.info("Dry-run mode — no files will be deleted.")
        return True
    if not sys.stdin.isatty():
        log.info("Non-interactive mode — proceeding automatically.")
        return True
    answer = input(f"\nDelete {count} folder(s)? (yes/no): ").strip().lower()
    return answer in ("yes", "y")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("SSH Storage Cleaner")
    log.info("Host: %s:%s  User: %s  Retain: %d days  DryRun: %s",
             SSH_HOST, SSH_PORT, SSH_USER, RETENTION_DAYS, DRY_RUN)
    log.info("=" * 60)

    if not SSH_HOST or not SSH_USER:
        log.error("SSH_HOST and SSH_USER must be set in .env")
        sys.exit(1)

    if not test_connection():
        sys.exit(1)

    folders = list_day_folders()
    if not folders:
        log.info("No date folders found — nothing to do.")
        return

    keep, to_delete = categorize(folders)

    log.info("Keep: %d  |  Delete: %d", len(keep), len(to_delete))

    if not to_delete:
        log.info("Nothing to delete — all folders are within retention period.")
        show_summary(keep, 0)
        return

    # Preview deletions (first 5)
    for f in to_delete[:5]:
        try:
            age = (datetime.date.today() - parse_folder_date(f)).days
            log.info("  Will delete: %s  (%d days old)", f, age)
        except Exception:
            log.info("  Will delete: %s", f)
    if len(to_delete) > 5:
        log.info("  … and %d more", len(to_delete) - 5)

    if not confirm(len(to_delete)):
        log.info("Cancelled.")
        return

    deleted = delete_folders(to_delete)
    remove_empty_parents()
    show_summary(keep, deleted)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Cancelled by user.")
        sys.exit(0)
