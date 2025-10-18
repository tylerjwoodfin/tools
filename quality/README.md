# Quality Scripts

This directory contains Python scripts for system maintenance and health monitoring.

## Scripts

### daily_maintenance.py

Performs daily maintenance tasks including dotfiles management and backup monitoring.

**Features:**
- **Dotfiles Application**: Runs `apply_stow.py` to ensure dotfiles are properly symlinked
- **Backup Monitoring**: Detects and warns about any files added or modified in `~/dotfiles-backup`
- **Change Detection**: Tracks file modifications before and after stow application
- **Comprehensive Logging**: All output logged to [Cabinet](https://github.com/tylerjwoodfin/cabinet)

**Example Scheduled Execution:**
```bash
# Runs daily at 3:00 AM via crontab
0 3 * * * /opt/homebrew/bin/python3 /Users/tyler/git/tools/quality/daily_maintenance.py
```

### service_check.py

Performs comprehensive system health checks.

**Features:**

**Docker Container Monitoring** (on `cloud` device only):
- **immich**: Checks if the immich Docker container is running
- **dawarich**: Checks if the dawarich Docker container is running

**System Service Monitoring** (on `cloud` device only):
- **rustdesk**: Checks if the rustdesk system service is active

**Disk Space Monitoring:**
- Monitors free disk space on the root filesystem
- Logs disk usage information to cabinet
- Warns when disk usage exceeds 90%

**Directory Structure Validation:**
- Verifies `~/syncthing` base directory exists
- Checks for required subfolders:
  - `documents`
  - `log`
  - `md`
  - `music`
  - `network`
  - `photos`

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure scripts have execute permissions:
```bash
chmod +x daily_maintenance.py service_check.py
```

3. Set up crontab for daily maintenance (optional):
```bash
crontab -e
# Add: 0 3 * * * /opt/homebrew/bin/python3 /Users/tyler/git/tools/quality/daily_maintenance.py
```

## Usage

### Daily Maintenance Script
Run manually:
```bash
python3 daily_maintenance.py
```

Or as an executable:
```bash
./daily_maintenance.py
```

The script runs automatically at 3:00 AM daily via crontab.

### Service Check Script
Run manually:
```bash
python3 service_check.py
```

Or as an executable:
```bash
./service_check.py
```

### Integration with Daily Status
The service check script is automatically integrated with the daily status system:

1. **Automatic Execution**: The daily status script (`tools/dailystatus/main.py`) automatically runs the service check before generating the daily report
2. **Data Collection**: Service check results are stored in [Cabinet](https://github.com/tylerjwoodfin/cabinet) for reporting
3. **Email Integration**: Service check results and disk space information are included in the daily status email

## Output

Both scripts provide detailed logging through [Cabinet](https://github.com/tylerjwoodfin/cabinet):
- ✓ Success indicators for running services and completed tasks
- ✗ Error indicators for failed checks
- ⚠ Warning indicators for high disk usage and backup file changes
- Detailed disk space information
- Directory structure validation results
- Dotfiles application status and backup monitoring

## Data Structure

The service check script stores data in Cabinet with the following structure:
```
quality:
  <device_name>:
    free_gb: <free_space_in_gb>
    updated_at: <timestamp>
```

This data is used by the daily status script to generate disk space tables in the email report.

## Requirements

- Python 3.6+
- [Cabinet](https://github.com/tylerjwoodfin/cabinet) logging system
- Docker (for container checks on `cloud`)
- systemctl (for service checks on `cloud`)

## Maintenance Tasks

The daily maintenance script ensures:
1. Dotfiles are kept in sync via stow
2. Backup conflicts are detected and reported
3. System remains consistent across reboots and updates
