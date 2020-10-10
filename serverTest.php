<?php

$sock = socket_create(AF_INET, SOCK_DGRAM, SOL_UDP);
socket_connect($sock,'127.0.0.1', 10000);

$msg = "Hello";
$len = strlen($msg);

socket_send($sock,$msg,$len,0);
socket_close($sock);
