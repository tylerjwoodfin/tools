#!/usr/bin/php

<?php
ini_set('display_errors', 1);
error_reporting(E_ALL);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $type = $_POST['type'];
    $log_file = "/var/www/html/log/log_bedtime.csv";
    $now = new DateTime();
    $date_str = $now->format('Y-m-d');
    $time_str = $now->format('H:i');

    // If the time is between midnight and 4AM, use yesterday's date instead
    if ($now->format('H') < 4) {
        $yesterday = (new DateTime())->sub(new DateInterval('P1D'));
        $date_str = $yesterday->format('Y-m-d');
    }

    $bedtime_exists_today = false;
    $wakeup_exists_today = false;

    // Check if log file exists, if not create it
    if(!file_exists($log_file)){
        $file = fopen($log_file, 'w');
        fputcsv($file, ['event', 'date', 'time']);
        fclose($file);
    }

    // Read the file content and check for "bedtime" or "wakeup"
    $file = fopen($log_file, 'r');
    $data = [];
    while (($line = fgetcsv($file)) !== FALSE) {
        if($line[0] == 'bedtime' && $line[1] == $date_str) {
            $line[2] = $time_str;  // update the time
            $bedtime_exists_today = true;
        } elseif($line[0] == 'wakeup' && $line[1] == $date_str) {
            $wakeup_exists_today = true;
        }
        $data[] = $line;
    }
    fclose($file);

    // Handle the bedtime
    if($type == 'bedtime') {
        if(!$bedtime_exists_today) {
            // append a new "bedtime" row
            $data[] = ['bedtime', $date_str, $time_str];
        }
        // rewrite the csv file
        $file = fopen($log_file, 'w');
        foreach($data as $line) {
            fputcsv($file, $line);
        }
        fclose($file);
    } elseif($type == 'wakeup' && $now->format('H') >= 4) {
        // handle the wakeup
        if(!$wakeup_exists_today) {
            // append a new "wakeup" row
            $data[] = ['wakeup', $date_str, $time_str];
            // rewrite the csv file
            $file = fopen($log_file, 'w');
            foreach($data as $line) {
                fputcsv($file, $line);
            }
            fclose($file);
        }
    }

    echo 'Updated Bedtime';
} else {
    echo 'Invalid request';
}
?>

