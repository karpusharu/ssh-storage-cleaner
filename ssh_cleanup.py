#!/usr/bin/env python3
"""
SSH Storage Cleaner - Delete old files from FTP/storage servers

A Python script to automatically delete old folders from storage servers
using SSH. Much faster than FTP - uses rm -rf for instant deletion.

Compatible with Hetzner Storage Boxes and other SSH-accessible storage.
"""

import subprocess
import datetime
import sys
import os
from typing import Tuple, List

# ============== CONFIGURATION ==============
SSH_HOST = "your-storagebox.de"
SSH_PORT = "23"  # Hetzner Storage Boxes use port 23
SSH_USER = "your-username"
RETENTION_DAYS = 7  # Keep last 7 days of recordings
BASE_DIR = ""  # Empty for home directory (where 2026 folder is located)

# Safety: Only delete folders matching this date pattern
FOLDER_PATTERN = r'/\d{4}/\d{2}/\d{2}$'  # Matches /2026/02/19 format


# ============== SSH FUNCTIONS ==============

def ssh_command(command: str, timeout: int = 600) -> Tuple[int, str, str]:
    """
    Execute a command via SSH.

    Args:
        command: The command to execute on the remote server
        timeout: Timeout in seconds (default: 600 = 10 minutes)

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    ssh_cmd = [
        "ssh",
        "-p", SSH_PORT,
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",  # Never ask for password (use SSH key)
        "-o", "ConnectTimeout=10",
        f"{SSH_USER}@{SSH_HOST}",
        command
    ]

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


def test_connection() -> bool:
    """Test SSH connection and display storage info."""
    print("Testing SSH connection...")

    code, out, err = ssh_command("pwd")

    if code != 0:
        print(f"✗ SSH connection failed!")
        print(f"Error: {err}")
        print("\nTroubleshooting:")
        print("1. Ensure SSH key is installed on the server")
        print(f"2. Test manually: ssh -p {SSH_PORT} {SSH_USER}@{SSH_HOST}")
        print("3. For Hetzner Storage Boxes, use: cat ~/.ssh/id_rsa.pub | ssh -p 23 user@host 'install-ssh-key'")
        return False

    print(f"✓ Connected! Current directory: {out}")

    # Show available disk space
    code, out, err = ssh_command("df -h .")
    if code == 0:
        print(f"\nStorage info:")
        print(out)

    return True


# ============== FOLDER MANAGEMENT ==============

def list_day_folders() -> List[str]:
    """
    List all day folders in the target directory.

    Returns:
        List of folder paths
    """
    print("\nScanning for folders...")

    base = BASE_DIR if BASE_DIR else "."

    # Get months/years
    code, output, err = ssh_command(f"ls {base}")
    if code != 0:
        print(f"Error listing directories: {err}")
        return []

    folders = []
    for month in output.split('\n'):
        if not month:
            continue

        # Skip files (only process directories)
        code2, days, err2 = ssh_command(f"test -d {base}/{month} && echo 'dir' || echo 'notdir'")
        if code2 != 0 or 'notdir' in days:
            continue

        # Get days in this month
        code, days, err = ssh_command(f"ls {base}/{month} 2>/dev/null")
        if code != 0:
            continue

        for day in days.split('\n'):
            if day and day.isdigit():
                folder_path = f"{base}/{month}/{day}" if base else f"{month}/{day}"
                folders.append(folder_path)

    print(f"Found {len(folders)} day folders")
    return folders


def parse_folder_date(folder_path: str) -> datetime.datetime:
    """Parse date from folder path like /2026/02/19."""
    parts = folder_path.rstrip('/').split('/')
    if len(parts) >= 3:
        try:
            year, month, day = int(parts[-3]), int(parts[-2]), int(parts[-1])
            return datetime.datetime(year, month, day)
        except (ValueError, TypeError):
            pass
    raise ValueError(f"Invalid folder format: {folder_path}")


def should_delete_folder(folder_path: str, retention_days: int) -> bool:
    """
    Check if a folder is older than the retention period.

    Args:
        folder_path: Path to the folder
        retention_days: Days to keep

    Returns:
        True if folder should be deleted
    """
    try:
        folder_date = parse_folder_date(folder_path)
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        return folder_date < cutoff_date
    except:
        return False


def delete_folder(folder_path: str) -> bool:
    """
    Delete a folder using rm -rf.

    Args:
        folder_path: Path to folder to delete

    Returns:
        True if successful
    """
    code, out, err = ssh_command(f"rm -rf '{folder_path}'")
    return code == 0


# ============== CLEANUP FUNCTIONS ==============

def categorize_folders(folders: List[str], retention_days: int) -> Tuple[List[str], List[str]]:
    """Separate folders into keep and delete lists."""
    to_delete = []
    to_keep = []

    for folder in folders:
        if should_delete_folder(folder, retention_days):
            to_delete.append(folder)
        else:
            to_keep.append(folder)

    return to_keep, to_delete


def delete_folders(folders: List[str]) -> int:
    """Delete folders and return count of successful deletions."""
    if not folders:
        return 0

    print(f"\nDeleting {len(folders)} old folders...")
    print("WARNING: This will permanently delete these folders!\n")

    deleted_count = 0

    for folder in folders:
        # Extract just the folder name for display
        folder_name = folder.replace(BASE_DIR, '').strip('/') if BASE_DIR else folder

        print(f"  Deleting {folder_name}...", end='', flush=True)

        if delete_folder(folder):
            deleted_count += 1
            print(" ✓")
        else:
            print(" ✗")

    return deleted_count


def cleanup_empty_parent_folders():
    """Remove empty month/year folders after deletion."""
    print("\nCleaning up empty parent folders...")

    base = BASE_DIR if BASE_DIR else "."

    # Try to remove empty directories
    code, out, err = ssh_command(f"find {base} -type d -empty -delete 2>/dev/null && echo 'Empty folders removed'")

    if out and 'Empty folders removed' in out:
        print("  ✓ Empty parent folders removed")


def show_summary(folders_kept: List[str], folders_deleted: int):
    """Display cleanup summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if folders_kept:
        print(f"\nKeeping {len(folders_kept)} folders (last {RETENTION_DAYS} days):")
        for folder in folders_kept[:10]:
            try:
                folder_date = parse_folder_date(folder)
                days_old = (datetime.datetime.now() - folder_date).days
                folder_name = folder.replace(BASE_DIR, '').strip('/') if BASE_DIR else folder
                print(f"  {folder_name} ({days_old} days old)")
            except:
                folder_name = folder.replace(BASE_DIR, '').strip('/') if BASE_DIR else folder
                print(f"  {folder_name}")

        if len(folders_kept) > 10:
            print(f"  ... and {len(folders_kept) - 10} more")

    print(f"\n✓ Total folders deleted: {folders_deleted}")
    print("=" * 60)


def confirm_deletion(folder_count: int) -> bool:
    """Ask user to confirm deletion."""
    # Check if running in non-interactive mode (cron)
    if not sys.stdin.isatty():
        # Running via cron - auto-confirm
        print(f"\nRunning in automatic mode - deleting {folder_count} folders.")
        return True

    # Running interactively - ask for confirmation
    print(f"\nAbout to delete {folder_count} folders older than {RETENTION_DAYS} days.")
    response = input("Continue? (yes/no): ").strip().lower()
    return response in ['yes', 'y']


# ============== MAIN ==============

def main():
    """Main cleanup function."""
    print("=" * 60)
    print("SSH Storage Cleaner")
    print("=" * 60)
    print("\nConfiguration:")
    print(f"  Host: {SSH_HOST}")
    print(f"  Port: {SSH_PORT}")
    print(f"  User: {SSH_USER}")
    print(f"  Retention: {RETENTION_DAYS} days")
    print(f"  Base Directory: {BASE_DIR or '(home directory)'}")
    print("-" * 60)

    # Check configuration
    if SSH_HOST == "your-storage-box.example.com":
        print("\n✗ Error: Please configure SSH_HOST, SSH_USER, and other settings")
        print("in the script before running.")
        sys.exit(1)

    # Test SSH connection
    if not test_connection():
        sys.exit(1)

    # List all folders
    folders = list_day_folders()
    if not folders:
        print("\nNo folders found to process.")
        return

    # Categorize folders
    to_keep, to_delete = categorize_folders(folders, RETENTION_DAYS)

    # Show what will be kept
    if to_keep:
        print(f"\nKeeping {len(to_keep)} folders:")
        for folder in to_keep[:5]:
            try:
                folder_date = parse_folder_date(folder)
                days_old = (datetime.datetime.now() - folder_date).days
                folder_name = folder.replace(BASE_DIR, '').strip('/') if BASE_DIR else folder
                print(f"  {folder_name} ({days_old} days old)")
            except:
                folder_name = folder.replace(BASE_DIR, '').strip('/') if BASE_DIR else folder
                print(f"  {folder_name}")

        if len(to_keep) > 5:
            print(f"  ... and {len(to_keep) - 5} more")

    # Show what will be deleted
    if to_delete:
        print(f"\nWill delete {len(to_delete)} folders:")
        for folder in to_delete[:5]:
            folder_name = folder.replace(BASE_DIR, '').strip('/') if BASE_DIR else folder
            print(f"  {folder_name}")

        if len(to_delete) > 5:
            print(f"  ... and {len(to_delete) - 5} more")

    # Confirm before deleting
    if not confirm_deletion(len(to_delete)):
        print("\n✗ Deletion cancelled.")
        return

    # Delete old folders
    deleted = delete_folders(to_delete)

    # Clean up empty parent folders
    cleanup_empty_parent_folders()

    # Show summary
    show_summary(to_keep, deleted)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Cleanup cancelled by user.")
        sys.exit(0)
