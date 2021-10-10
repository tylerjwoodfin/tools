# ReadMe
# This is a simple module to send mail through smtplib.
# For Gmail, you will need to enable "less secure apps".
# 
# This is called from a wrapper function in /usr/sbin/rmail. 
# I'm using unquote (a.k.a. URL decode) for each parameter in case this is being called from web servers or from other
# scripts with the need to escape quotation characters.

# Dependency: https://github.com/tylerjwoodfin/SecureData

import smtplib
from urllib.parse import unquote
import ssl
import sys
import pwd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

userDir = pwd.getpwuid( os.getuid() )[ 0 ]

sys.path.insert(0, f'/home/{userDir}/Git/SecureData')
import secureData

# Parameters
port = 465
smtp_server = "smtp.gmail.com"
username = secureData.variable("email_pi")
password = secureData.variable("email_pi_pw")

def send(subject, body, signature="<br><br>Thanks,<br>Raspberry Pi", to=secureData.variable("email")):    
    
    # Parse
    body += unquote(signature)
    message = MIMEMultipart()
    message["Subject"] = unquote(subject)
    message["From"] = "Raspberry Pi <" + username + ">"
    message["To"] = secureData.variable("email")
    message.attach(MIMEText(unquote(body), "html"))

    # Send Email
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(username, password)
        server.sendmail(message["From"], message["To"], message.as_string())
        secureData.log(f"Sent Email: {sys.argv[1]}")
   
# By default, mail.send:     
if(len(sys.argv) == 3):
    send(sys.argv[1], sys.argv[2])
    secureData.log(f"Sent Email: {sys.argv[1]}")

if __name__ == "__main__":
	if(len(sys.argv) == 1):
    		print("Usage: sendMail <subject>, <body>, <signature>, <to_email>")
