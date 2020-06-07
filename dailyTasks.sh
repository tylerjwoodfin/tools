# ReadMe
# This grabs my Tasks file from Nextcloud, then emails it to me.
# Usage: sudo bash sendMail.sh

#!/bin/sh

# Read certain variables from the secure data folder
tasks=$(<SecureData/nextCloudRootDirectory)
email_pi=$(<SecureData/email_pi)
email=$(<SecureData/email)

body="
<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01 Transitional//EN\" \"http://www.w3.org/TR/html4/loose.dtd\">
<html>
<head><title></title>
</head>
<body>
Dear Tyler,<br><br>
Please review the following tasks:<br><font face='monospace'>"

# Replace \n with <br> and replace ' ' with &nbsp;
tasks=$(sed -e 's|^|<br>|' -e 's|\s|\&nbsp;|g' $tasks/Notes/Tasks.txt)

body="$body$tasks"
echo "$body"

echo $body | mail \
-a "From: $email_pi" \
-a "MIME-Version: 1.0" \
-a "Content-Type: text/html" \
-s "Daily Tasks Review" \
$email