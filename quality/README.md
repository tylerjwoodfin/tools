# Service Check Script

This Python script performs comprehensive system health checks including:

## Features

### Docker Container Monitoring
- **immich**: Checks if the immich Docker container is running
- **dawarich**: Checks if the dawarich Docker container is running

### System Service Monitoring
- **rustdesk**: Checks if the rustdesk system service is active

### Disk Space Monitoring
- Monitors free disk space on the root filesystem
- Logs disk usage information to cabinet
- Warns when disk usage exceeds 90%

### Directory Structure Validation
- Verifies `~/syncthing` base directory exists
- Checks for required subfolders:
  - `documents`
  - `log`
  - `md`
  - `music`
  - `network`

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure the script has execute permissions:
```bash
chmod +x service_check.py
```

## Usage

### Standalone Usage
Run the script directly:
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
2. **Data Collection**: Service check results are stored in the Cabinet system for reporting
3. **Email Integration**: Service check results and disk space information are included in the daily status email

## Output

The script provides detailed logging through the Cabinet system:
- ✓ Success indicators for running services
- ✗ Error indicators for failed checks
- ⚠ Warning indicators for high disk usage
- Detailed disk space information
- Directory structure validation results

## Data Structure

The script stores data in Cabinet with the following structure:
```
quality:
  <device_name>:
    free_gb: <free_space_in_gb>
```

This data is used by the daily status script to generate disk space tables in the email report.

## Testing

Run the test script to verify functionality:
```bash
python3 test_service_check.py
```

## Requirements

- Python 3.6+
- Docker (for container checks)
- systemctl (for service checks)
- Cabinet logging system
- psutil library
