# MySQL

## Overview

To access, use:
> sudo mysql -u root -p

Then enter the root password.

## Error 1405 Workaround:
> sudo systemctl mysql stop
> sudo /usr/sbin/mysqld --skip-grant-tables --skip-networking &

> update mysql.user set password=password('newpass') where user='root';
> flush privileges;
> update mysql.user set plugin='mysql_native_password' where user='root';
> flush privileges;

Then restart the database
