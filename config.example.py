"""
Configuration Example for SSH Storage Cleaner

Copy this file to config.py and fill in your actual values.
DO NOT commit config.py to version control!
"""

# SSH Server Configuration
SSH_HOST = "your-storage-box.example.com"
SSH_PORT = "22"  # Use "23" for Hetzner Storage Boxes
SSH_USER = "your-username"

# Retention Settings
RETENTION_DAYS = 14  # Delete folders older than this many days

# Directory Settings
BASE_DIR = ""  # Empty for home directory, or specify like "/data"

# Optional: Only process specific years (uncomment to use)
# TARGET_YEARS = ["2026", "2025"]  # Only process these years

# Optional: Skip specific months (uncomment to use)
# SKIP_MONTHS = ["12"]  # Don't delete December data

# Safety Settings
CONFIRM_BEFORE_DELETE = True  # Always ask for confirmation
DRY_RUN = False  # Set to True to simulate deletion without actually deleting
