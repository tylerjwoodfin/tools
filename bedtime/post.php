#!/usr/bin/php

<?php
ini_set('display_errors', 1);
error_reporting(E_ALL);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $type = $_POST['type'];
    $timezone = $_POST['timezone'];
    $log_file = "/var/www/html/log/log_bedtime.csv";
    $now = new DateTime();
    $date_str = $now->format('Y-m-d');
    $time_str = $now->format('H:i');
    
    // Read JSON data from the file
    $bedtime_config_file = '/home/tyler/syncthing/cabinet/keys/BEDTIME';
    $timezone_config_file = '/home/tyler/syncthing/cabinet/keys/TIMEZONE';
    $bedtime_config_json = file_get_contents($bedtime_config_file);
    $bedtime_config = json_decode($bedtime_config_json, true);

    if (json_last_error() !== JSON_ERROR_NONE) {
        // Handle the error if JSON is not valid
        echo "Error decoding JSON: " . json_last_error_msg();
        exit;
    }

    // write timezone
    file_put_contents($timezone_config_file, $timezone);

    // Extract values from JSON data
    $charity_balance = $bedtime_config['charity_balance'];
    $bedtime_limit_str = $bedtime_config['max_bedtime'];
    $max_donation = $bedtime_config['max_penalty']; // Max penalty from the JSON file
    $bedtime_limit = new DateTime($bedtime_limit_str);

    // If current time is between midnight and 4AM, use yesterday's date instead
    if ($now->format('H') < 4) {
        $yesterday = (new DateTime())->sub(new DateInterval('P1D'));
        $date_str = $yesterday->format('Y-m-d');
    }

    // If current time is after midnight but before 6 AM, consider the bedtime limit for the previous day
    if ($now->format('H') < 6) {
        if ($bedtime_limit->format('H') >= 6) {
            $bedtime_limit->modify('-1 day');
        }
    }

    // If bedtime limit is between midnight and 4AM, but
    // the current time is between 8PM and 11:59PM, set bedtime limit date to tomorrow
    if ($now->format('H') >= 20 && $bedtime_limit->format('H') < 4) {
        $tomorrow = (new DateTime())->add(new DateInterval('P1D'));
        $bedtime_limit->setDate($tomorrow->format('Y'), $tomorrow->format('m'), $tomorrow->format('d'));
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
    
    // Calculate time difference in minutes
    $interval = $now->diff($bedtime_limit);
    $delta_minutes = ($interval->h * 60) + $interval->i;

    if ($now > $bedtime_limit && $now <= new DateTime('06:00')) {
        // Late bedtime
        $donation_amount = min($delta_minutes, $max_donation);
        echo "Updated Bedtime; {$donation_amount} dollar donation is required";
    } elseif ($now < $bedtime_limit) {
        // Early bedtime
        $refund_amount = min($delta_minutes / 2, $max_donation / 2); // 50% refund, capped at half of max penalty
        echo "Sleep now for {$refund_amount} dollar refund.";
    } else {
        // Bedtime is after midnight
        echo "Updated Bedtime";
        echo $timezone;
    }
} else {
    echo 'Invalid request';
}
?>

