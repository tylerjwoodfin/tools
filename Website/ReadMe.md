# OVERVIEW

This contains tools for managing my website.

# StartLocalServer.sh
This uses Python to start a local server for tyler.cloud on port 8000 to test locally

# Databases/MySQL
In the Pi Terminal, at /var/www/html:
> sudo mysql

> use [database name here]; (e.g. "use TylerDotCloud")

# Tables
GAME:
- GameID [pk int auto increment]
- GameName [varchar]

SCORE:
- ScoreID [pk int auto increment]
- ScoreDate [datetime (default to now()]
- PlayerName [varchar]
- Score [int]
- GameID [fk]

- Use **view tables;** to list current MySQL tables, and use traditional SQL commands to view data.