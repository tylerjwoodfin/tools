# Bedtime Logger
A simple script to log my bedtime/wakeup time, triggered via a HTTP POST to my server from my phone via Tasker.

## Usage
`POST http://<server:port/path>?type={bedtime/wakeup}`

## Requirements
- Python 3.x
- PHP 5.x or later

## Configuration
- The path to the log file is set in the LOG_FILE variable in log.py. By default, it is set to /home/tyler/syncthing/log/log_bedtime.csv.
- The script assumes that the log file is in CSV format with three columns: 'bedtime/wakeup', 'YYYY-MM-DD', and 'HH:mm'.
- The PHP script should be placed in a web-accessible directory on your server, such as /var/www/html/bedtime/post.php.
