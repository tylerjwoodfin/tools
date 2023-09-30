<?php 
ini_set('display_errors', 1); 
error_reporting(E_ALL);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $steps = (int) str_replace(',', '', $_POST['steps']); // Ensure that $steps is an integer
    $log_file = "/var/www/html/log/log_steps.csv";
    $syncthing_file = "/home/tyler/syncthing/log/log_steps.csv"; // The location of the Syncthing folder.
    
    $now = new DateTime();
    $date_str = $now->format('Y-m-d');

    // Check if log file exists, if not create it
    if(!file_exists($log_file)){
        $file = fopen($log_file, 'w');
        if(!$file) {
            echo 'Error: Unable to open log file for writing.';
            exit;
        }
        fputcsv($file, ['date', 'steps']);
        fclose($file);
    }

    // Read the file content and check if steps are already logged for today
    $file = fopen($log_file, 'r');
    if(!$file) {
        echo 'Error: Unable to open log file for reading.';
        exit;
    }
    $data = []; 
    $steps_exists_today = false;
    while (($line = fgetcsv($file)) !== FALSE) {
        if($line[0] == $date_str) {
            $line[1] = $steps;  // update the steps
            $steps_exists_today = true;
        }
        $data[] = $line;
    }   
    fclose($file);

    // Append a new row if steps are not yet logged for today
    if(!$steps_exists_today) {
        $data[] = [$date_str, $steps];
    }

    // Rewrite the csv file
    $file = fopen($log_file, 'w');
    if(!$file) {
        echo 'Error: Unable to open log file for writing.';
        exit;
    }
    foreach($data as $line) {
        fputcsv($file, $line);
    }
    fclose($file);

    // After updating the $log_file, copy it to $syncthing_file
    if(!copy($log_file, $syncthing_file)) {
        echo 'Error: Unable to copy log file to Syncthing directory.';
        exit;
    }

    echo 'Steps updated';
} else {
    echo 'Invalid request';
}
?>

