import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from typing import Optional, List

# Hardcoded email credentials
# Replace these with your actual email credentials if  needed
EMAIL_USER = "admin@example.com"
EMAIL_PASSWORD = "your_password"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def send_email_notification(subject, body, recipient=None):
    """
    Send email notification
    If recipient is provided, send to that recipient
    Otherwise, send to the business owner
    """
    try:
        # If email credentials are not all set, just log the message
        if not all([EMAIL_USER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT]):
            print(f"Email notification would be sent: {subject}\n{body}")
            return {"status": "logged", "message": "Email credentials not set, notification logged"}
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        
        # If recipient is provided, send to that recipient
        # Otherwise, send to the business owner
        msg['To'] = recipient if recipient else EMAIL_USER
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return {"status": "success", "message": "Email notification sent"}
    
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")
        return {"status": "error", "message": str(e)} 