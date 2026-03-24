# SSH Storage Cleaner

A Python script to automatically delete old folders from storage servers using SSH. Much faster than FTP-based cleanup - uses `rm -rf` for instant deletion of entire directories.

## Features

- ⚡ **Fast deletion** - Deletes entire folders in seconds using SSH
- 🔒 **Safe operation** - Only deletes folders matching date pattern (YYYY/MM/DD)
- 🎯 **Configurable retention** - Keep data for a specified number of days
- 📊 **Progress tracking** - See what's being deleted in real-time
- 🔑 **SSH key authentication** - No passwords in scripts

## Use Cases

- **Security camera footage cleanup** - Automatically delete old recordings
- **Log file rotation** - Clean up dated log directories
- **Backup retention** - Remove backups older than X days
- **Any dated folder structure** - Works with YYYY/MM/DD format

## Compatibility

- ✅ Hetzner Storage Boxes (port 23)
- ✅ Any SSH-accessible server (port 22)
- ✅ Linux/Unix systems
- ✅ macOS
- ✅ Windows (with WSL or Git Bash)

## Installation

### 1. Clone or download this script

```bash
git clone <repository-url>
cd ssh-storage-cleaner
```

### 2. Configure the script

Edit `ssh_cleanup.py` and update the configuration at the top:

```python
SSH_HOST = "your-storage-box.example.com"
SSH_PORT = "22"  # Use "23" for Hetzner Storage Boxes
SSH_USER = "your-username"
RETENTION_DAYS = 14
BASE_DIR = ""  # Empty for home directory
```

### 3. Set up SSH key authentication

**For most servers:**
```bash
ssh-copy-id -p PORT user@hostname
```

**For Hetzner Storage Boxes:**
```bash
cat ~/.ssh/id_rsa.pub | ssh -p 23 user@hostname 'install-ssh-key'
```

**Test connection:**
```bash
ssh -p PORT user@hostname
```

## Usage

### Basic usage

```bash
python3 ssh_cleanup.py
```

The script will:
1. Test SSH connection
2. Scan for date-formatted folders (YYYY/MM/DD)
3. Show what will be kept vs deleted
4. Ask for confirmation
5. Delete old folders
6. Clean up empty parent folders
7. Show summary

### Dry run (see what would be deleted)

To see what would be deleted without actually deleting, you can comment out the actual `rm -rf` command in the `delete_folder()` function.

### Schedule automatic cleanup

**Using cron (Linux/macOS):**
```bash
# Edit crontab
crontab -e

# Add: Run daily at 3 AM
0 3 * * * /usr/bin/python3 /path/to/ssh_cleanup.py >> /var/log/ssh_cleanup.log 2>&1
```

**Using Task Scheduler (Windows):**
Create a scheduled task to run the script with WSL or Git Bash.

## Safety Features

### Only deletes date-formatted folders

The script only processes folders matching the pattern: `/YYYY/MM/DD`

This prevents accidental deletion of:
- Configuration files
- Other directories
- System files

### Confirmation prompt

The script always asks for confirmation before deleting, unless you modify it.

### SSH key authentication

No passwords stored in scripts - uses secure SSH key authentication.

## Configuration Options

| Setting | Description | Example |
|---------|-------------|---------|
| `SSH_HOST` | Server hostname | `"storage.example.com"` |
| `SSH_PORT` | SSH port | `"22"` (standard) or `"23"` (Hetzner) |
| `SSH_USER` | SSH username | `"admin"` |
| `RETENTION_DAYS` | Days to keep | `14` (keep 14 days, delete older) |
| `BASE_DIR` | Base directory | `""` (home) or `"/data"` |

## Examples

### Example 1: Security camera footage

```python
SSH_HOST = "camera-storage.example.com"
SSH_PORT = "22"
SSH_USER = "admin"
RETENTION_DAYS = 30  # Keep 30 days of footage
BASE_DIR = "/recordings"
```

Folder structure: `/recordings/2026/02/19/`

### Example 2: Hetzner Storage Box

```python
SSH_HOST = "u123456.your-storagebox.de"
SSH_PORT = "23"  # Hetzner uses port 23
SSH_USER = "u123456"
RETENTION_DAYS = 14
BASE_DIR = ""  # Home directory
```

Folder structure: `/home/u123456/2026/02/19/`

### Example 3: Log cleanup

```python
SSH_HOST = "logs.example.com"
SSH_PORT = "22"
SSH_USER = "logadmin"
RETENTION_DAYS = 7  # Keep 7 days of logs
BASE_DIR = "/var/log/app"
```

Folder structure: `/var/log/app/2026/02/19/`

## Troubleshooting

### SSH connection fails

1. Test SSH manually: `ssh -p PORT user@host`
2. Check SSH key is installed on server
3. For Hetzner: Use the `install-ssh-key` command
4. Verify SSH config: `~/.ssh/config`

### Permission denied

- Ensure your SSH key is added to the server
- Check file permissions on target directories
- Verify user has delete permissions

### Folders not being found

- Check `BASE_DIR` setting
- Verify folder structure matches YYYY/MM/DD pattern
- Test path manually: `ssh user@host "ls /path/to/folder"`

### Timeout errors

Large folders with thousands of files may take time to delete. The default timeout is 10 minutes (600 seconds). You can increase this in the `ssh_command()` function if needed.

## Comparison: SSH vs FTP

| Method | Speed | 1000 files | 10000 files |
|--------|-------|-----------|-------------|
| **FTP (file-by-file)** | Very slow | ~5 min | ~45 min |
| **SSH (rm -rf)** | Instant | ~2 sec | ~10 sec |

SSH is **100x faster** for bulk deletion because it uses server-side `rm -rf` instead of deleting files individually over the network.

## Requirements

- Python 3.6 or higher
- SSH access to target server
- SSH key authentication (no passwords)
- Standard tools: `ssh`, `rm`, `ls`

## License

MIT License - Feel free to use and modify.

## Contributing

Contributions welcome! Please feel free to submit pull requests or open issues.

## Disclaimer

This script deletes files permanently. Always test on non-critical data first and ensure you have backups. The authors are not responsible for data loss.
