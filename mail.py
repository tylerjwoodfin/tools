import smtplib
import ssl
import secureData
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Parameters
port = 465
smtp_server = "smtp.gmail.com"
password = secureData.variable("email_pi_pw")

def send(subject, body, signature="<br><br>Thanks,<br>Raspberry Pi", to=secureData.variable("email")):    
    
    # Parse
    body += signature
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = secureData.variable("email_pi")
    message["To"] = secureData.variable("email")
    message.attach(MIMEText(body, "html"))

    # Send Email
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(message["From"], password)
        server.sendmail(message["From"], message["To"], message.as_string())
        print("Sent Email")