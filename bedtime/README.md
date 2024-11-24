# Bedtime Logger

The Bedtime Logger is a system that tracks and enforces a set bedtime by logging sleep times and adjusting a "charity balance" based on whether the user goes to bed early or late. The system has two main components: a Python script for logging and calculating penalties or refunds, and a PHP API for logging bedtimes and wake-up times and calculating time differences for determining penalties or refunds.

## Disclaimer
This is for my personal use and is not guaranteed to work for everyone. It is simply a fun project to help me get to bed on time.

## Features

1. **Log Bedtimes and Wakeup Times**: The PHP API logs `bedtime` and `wakeup` events in a CSV file, creating entries based on the current date and time.
2. **Enforce Bedtime**: The system sets a bedtime limit. If the user goes to bed late, it charges a penalty (donated to a "charity balance"). If the user goes to bed early, a partial refund is applied.
3. **Calculate Penalty and Refund**: The Python script calculates the time difference between the actual bedtime and the bedtime limit, applying a donation or refund to the charity balance.
4. **Notification**: The system sends an email alert when a penalty or refund is processed, providing feedback to the user on their sleep habits.

## Components

### 1. PHP API (`bedtime.php`)
Handles POST requests to log bedtime and wakeup events. It performs the following tasks:
- **Log Bedtime**: Appends or updates the bedtime time in the log file (`log_bedtime.csv`).
- **Log Wakeup**: Logs wake-up times if the current time is after 4 AM.
- **Calculate Penalties or Refunds**: Checks the current time against the bedtime limit. If late, a penalty is calculated; if early, a refund is issued.

### 2. Python (`check_bedtime.py`)
Processes the bedtime log file and calculates the time difference between the bedtime limit and actual bedtime:
- **Parse the CSV File**: Reads the bedtime from the log file.
- **Calculate Time Difference**: Determines if the bedtime was late or early, adjusting for crossing midnight.
- **Adjust Charity Balance**: Applies a penalty or a refund to the charity balance and logs these updates in the cabinet configuration.
- **Email Notification**: Sends an email notification when a penalty or refund is applied.

### Configuration

- **Cabinet Configuration**: The Python script uses [Cabinet](https://pypi.org/project/cabinet/) to store and retrieve bedtime settings, such as the maximum penalty, bedtime limit, and charity balance.
- **Log File**: The `log_bedtime.csv` file stores daily `bedtime` and `wakeup` entries.
- **Mail**: The `Mail` class (part of Cabinet) sends email notifications to alert the user of late bedtimes and applied refunds.

## Installation

1. Place the PHP script in a server location accessible by your web server, ensuring PHP is configured to run the script.
2. Place the Python script in a suitable location and set up a scheduled job (e.g., cron job) to run it periodically.
3. Configure [Cabinet](https://pypi.org/project/cabinet/) to store the bedtime limit, charity balance, and maximum penalty:
    - See this example:
```json
{
    "bedtime": {
        "limit": {
            "max_bedtime": "23:00",         // Sample bedtime limit
            "max_penalty": 20,              // Maximum penalty for late bedtime in dollars
            "charity_balance": 50           // Current charity balance amount
        }
    }
}
```

4. Ensure that both PHP and Python scripts have the necessary permissions to read/write the CSV and JSON configuration files.

## Usage

### Logging Bedtime and Wakeup Events

- Send a `POST` request to `bedtime.php` with the following parameters:
  - `type`: Specifies the type of event, either `bedtime` or `wakeup`.
  - `timezone`: Sets the user's timezone for accurate time calculations.
  
Example:
```bash
curl -X POST -F 'type=bedtime' -F 'timezone=America/Los_Angeles' http://yourserver/bedtime.php
```

### Checking and Updating Bedtime Status

1. Run the Python script to check if the logged bedtime meets the limit:
   - If late, the charity balance is increased by the penalty amount.
   - If early, the charity balance is reduced by 50% of the time difference penalty.

### Penalty and Refund Calculation

1. If bedtime is late, the penalty is the minimum of the time difference (in minutes) and the maximum penalty.
2. If bedtime is early, the refund is 50% of the time difference, capped at half the maximum penalty.

## Files and Configuration

- **`log_bedtime.csv`**: Stores daily records of bedtime and wake-up events.
- **`/cabinet/keys/BEDTIME`**: JSON file storing bedtime limit, charity balance, and maximum penalty.
- **`/cabinet/keys/TIMEZONE`**: Text file storing the user’s timezone.

## Example Workflow

1. Log your bedtime by sending a `POST` request to `bedtime.php`.
2. The PHP script records the bedtime and compares it to the configured bedtime limit.
3. If bedtime is late, it applies a penalty; if early, it calculates a refund.
4. The Python script checks the log file daily to enforce penalties or apply refunds and sends an email notification with updated charity balance details.

## License

MIT License