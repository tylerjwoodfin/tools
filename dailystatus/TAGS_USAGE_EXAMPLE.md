# Using Tags in Daily Status Logs

## Overview
The Cabinet logging system now supports optional tags for categorizing log entries and a `log_query()` function for searching logs by various criteria.

## Basic Usage

### Logging with Tags

```python
import cabinet

cab = cabinet.Cabinet()

# Single tag
cab.log("Checked weather successfully", tags=["weather"])

# Multiple tags
cab.log("Starting Borg Backup...", tags=["backup", "start"])
cab.log("Pruning repository", tags=["backup", "prune"])
cab.log("Compacting repository", tags=["backup", "compact"])

# Without tags (backward compatible)
cab.log("Regular log message")
```

### Log Format

Logs with tags appear as:
```
2025-09-27 02:01:09,012 — INFO [weather] -> tools/weather.py:116@cloud -> Checked weather successfully
2025-09-27 03:05:03,732 — INFO [backup,start] -> bin/cabinet:8@cloud -> Starting Borg Backup...
2025-09-27 03:05:24,861 — INFO [backup,prune] -> bin/cabinet:8@cloud -> Pruning repository
2025-09-27 03:05:27,111 — INFO [backup,compact] -> bin/cabinet:8@cloud -> Compacting repository
```

## Querying Logs

### Basic Queries

```python
from datetime import date

cab = cabinet.Cabinet()
today = str(date.today())
log_file = f"LOG_DAILY_{today}.log"

# Query by tag
results = cab.log_query(log_file, tags=["weather"])

# Query by multiple tags (returns logs with any of these tags)
results = cab.log_query(log_file, tags=["backup", "weather"])

# Query by log level
results = cab.log_query(log_file, level="ERROR")

# Query by message content (case-insensitive)
results = cab.log_query(log_file, message="repository")

# Query by file path (fuzzy search)
results = cab.log_query(log_file, path="cabinet")

# Query by hostname
results = cab.log_query(log_file, hostname="cloud")
```

### Combined Queries

```python
# Find all INFO-level backup logs
results = cab.log_query(
    log_file,
    tags=["backup"],
    level="INFO"
)

# Find all error logs containing "failed"
results = cab.log_query(
    log_file,
    level="ERROR",
    message="failed"
)

# Find all weather logs from a specific date
results = cab.log_query(
    log_file,
    tags=["weather"],
    date_filter="2025-09-27"
)
```

## Integration in main.py

Here are examples of how to integrate tags into the `dailystatus/main.py`:

### Service Check
```python
def run_service_check():
    """Run the service check script and log any issues"""
    # ...existing code...
    try:
        subprocess.run([sys.executable, service_check_script], ...)
        cab.log("Service check completed successfully", tags=["service", "check"])
        return True
    except subprocess.CalledProcessError as e:
        cab.log(f"Service check failed: {e.stderr}", level="error", tags=["service", "check", "error"])
        return False
```

### Food Log
```python
def append_food_log(email):
    """check if food has been logged today"""
    # ...existing code...
    if not os.path.exists(log_file):
        cab.log("Food log file does not exist.", level="error", tags=["food", "error"])
        return email
    
    if today not in log_data or not log_data[today]:
        cab.log("No food logged for today.", level="error", tags=["food", "missing"])
        return email
    else:
        total_calories = sum(entry["calories"] for entry in log_data[today])
        cab.log(f"Food logged: {total_calories} calories", tags=["food", "success"])
        # ...
```

### Spotify
```python
def append_spotify_info(paths, email):
    """append spotify issues and stats"""
    # ...existing code...
    if spotify_log:
        cab.log("Spotify stats retrieved", tags=["spotify", "stats"])
    # ...
```

## Querying for Analysis

You can create a new function to analyze logs by category:

```python
def analyze_logs_by_category():
    """Analyze today's logs by category"""
    today = str(date.today())
    log_file = f"LOG_DAILY_{today}.log"
    
    categories = {
        "Weather": ["weather"],
        "Backup": ["backup"],
        "Service": ["service", "check"],
        "Food": ["food"],
        "Spotify": ["spotify"]
    }
    
    print("\n=== Log Analysis by Category ===\n")
    
    for category, tags in categories.items():
        results = cab.log_query(log_file, tags=tags)
        print(f"{category}: {len(results)} entries")
        
        # Count errors in this category
        errors = cab.log_query(log_file, tags=tags, level="ERROR")
        if errors:
            print(f"  - {len(errors)} errors")
            for error in errors:
                print(f"    • {error}")
```

## Benefits

1. **Easy Filtering**: Quickly find all logs related to a specific operation
2. **Category Analysis**: Group logs by functionality (backup, weather, spotify, etc.)
3. **Error Tracking**: Find all errors in a specific category
4. **Performance Monitoring**: Track how long certain operations take
5. **Debugging**: Quickly locate logs from specific code paths

## Note

- Tags are **optional** - existing code without tags will continue to work
- Tags are **case-sensitive**
- Use consistent tag names across your codebase for easier querying
- Multiple tags can be combined for fine-grained categorization

