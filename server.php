<?php

$sock = socket_create(AF_INET, SOCK_DGRAM, SOL_UDP);
socket_bind($sock, '0.0.0.0', 10000);

for (;;) {
    socket_recvfrom($sock, $message, 1024, 0, $ip, $port);

    $message = explode("\n",$message)[0];
    // $reply = str_rot13($message);
    // socket_sendto($sock, $reply, strlen($reply), 0, $ip, $port);

   if($message === "hello") {
       socket_sendto($sock, "Match\n", 8, 0, $ip, $port);
       shell_exec('python3 /home/pi/Tools/SmartBulb/alert.py');
   }
   else {
       $len=strlen($message);
       socket_sendto($sock, "\n.$message.$len\n",100, 0, $ip, $port);
   }
}
