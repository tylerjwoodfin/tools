<?php ini_set('display_errors', 1); error_reporting(E_ALL);
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Handle the POST request
    $type = $_POST['type'];
    // Run the Python script and capture the output
    exec("/usr/bin/python3 /home/tyler/git/tools/bedtime/log.py $type 2>&1", $output, $return_var);
    echo("Updated Bedtime");
    // Print the output of the Python script
    foreach ($output as $line) {
        echo $line . "\n";
    }
} else {
    // Not a POST request, ignore it
    echo 'Invalid request';
}

?>