# Bedtime Logger
A simple script to log my bedtime/wakeup time, triggered via a HTTP POST to my server from my phone via Tasker.

## Usage
`POST http://<server:port/path/to/post.php>?type={bedtime/wakeup}`

## Requirements
- PHP 5.x or later
- [Tasker](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm) (optional)

## Configuration
- In `post.php`, adjust the path to your own user folder.
- The path to the log file is set in the LOG_FILE variable in log.py. By default, it is set to /home/tyler/syncthing/log/log_bedtime.csv.
- The script assumes that the log file is in CSV format with three columns: 'bedtime/wakeup', 'YYYY-MM-DD', and 'HH:mm'.
- The PHP script should be placed in a web-accessible directory on your server, such as /var/www/html/bedtime/post.php.

## Tasker Configuration (optional)
- To use this with Tasker, import the profiles provided in `tasker-profiles` and adjust according to your own setup

## Disclaimers
- Use webservers with caution and limit access from the internet to your server.
- This project is for educational uses only, and no guarantees can be made as to the accuracy or safety of instructions provided here.
    - Specifically, modifying directory permissions to provide executable access to `www-data` is inherently risky.
