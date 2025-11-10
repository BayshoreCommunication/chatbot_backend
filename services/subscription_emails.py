"""
Subscription Email Notification Service
Handles all subscription-related email notifications
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from datetime import datetime
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.getenv("SMPT_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMPT_PORT", "465"))
SMTP_MAIL = os.getenv("SMPT_MAIL", "bayshoreai@gmail.com")
SMTP_PASSWORD = os.getenv("SMPT_PASSWORD", "rcwasfkrlkvshxbd")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send email using SMTP"""
    try:
        # Validate configuration
        if not SMTP_PASSWORD or not SMTP_MAIL:
            logger.error("❌ SMTP configuration incomplete: Missing password or email")
            logger.error(f"SMTP_MAIL: {SMTP_MAIL}, SMTP_PASSWORD: {'SET' if SMTP_PASSWORD else 'NOT SET'}")
            return False
        
        logger.info(f"📧 Preparing email to {to_email}")
        logger.info(f"📧 Subject: {subject}")
        logger.info(f"📧 SMTP Config: {SMTP_HOST}:{SMTP_PORT}")
        
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_MAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        logger.info(f"🔌 Connecting to SMTP server...")
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            logger.info(f"🔐 Authenticating as {SMTP_MAIL}...")
            server.login(SMTP_MAIL, SMTP_PASSWORD)
            logger.info(f"📤 Sending email...")
            server.send_message(msg)
            
        logger.info(f"✅ Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ SMTP Authentication failed: {str(e)}")
        logger.error(f"❌ Check SMTP_MAIL ({SMTP_MAIL}) and SMTP_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP error sending to {to_email}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        return False


def send_subscription_confirmation_email(
    to_email: str,
    customer_name: str,
    plan_name: str,
    amount: float,
    billing_cycle: str,
    subscription_start: str,
    subscription_end: str
) -> bool:
    """Send subscription confirmation email"""
    subject = f"🎉 Welcome to {plan_name} - Subscription Confirmed!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 0; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .content {{ background: #f9f9f9; padding: 30px 20px; }}
            .details-box {{ background: white; padding: 25px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
            .detail-row {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .detail-label {{ font-weight: bold; color: #667eea; }}
            .button {{ background: #667eea; color: white; padding: 14px 35px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 20px 0; font-weight: bold; }}
            .button:hover {{ background: #5568d3; }}
            .features {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .features ul {{ margin: 10px 0; padding-left: 20px; }}
            .features li {{ padding: 5px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; background: #e9e9e9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Payment Successful!</h1>
                <p style="margin: 10px 0 0 0; font-size: 16px;">Welcome to {plan_name}</p>
            </div>
            
            <div class="content">
                <p>Hi <strong>{customer_name}</strong>,</p>
                <p>Thank you for subscribing to our AI Assistant! Your payment has been processed successfully, and your subscription is now active.</p>
                
                <div class="details-box">
                    <h3 style="margin-top: 0; color: #667eea;">📋 Subscription Details</h3>
                    <div class="detail-row">
                        <span class="detail-label">Plan:</span> {plan_name}
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Amount Paid:</span> ${amount:.2f}
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Billing Cycle:</span> {billing_cycle.capitalize()}
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Subscription Start:</span> {subscription_start}
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Next Billing Date:</span> {subscription_end}
                    </div>
                </div>
                
                <div class="features">
                    <h3 style="margin-top: 0; color: #667eea;">✨ What's Included:</h3>
                    <ul>
                        <li>✅ Full access to AI Assistant features</li>
                        <li>✅ Priority customer support</li>
                        <li>✅ Advanced analytics and insights</li>
                        <li>✅ Custom integrations</li>
                        <li>✅ Regular feature updates</li>
                    </ul>
                </div>
                
                <div style="text-align: center;">
                    <a href="{FRONTEND_URL}/dashboard" class="button">Access Your Dashboard</a>
                </div>
                
                <p style="margin-top: 30px;">If you have any questions or need assistance, please don't hesitate to reach out to our support team.</p>
                
                <p style="margin-top: 20px;">Best regards,<br><strong>AI Assistant Team</strong></p>
            </div>
            
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
                <p>You're receiving this email because you subscribed to our service.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def send_subscription_expiry_warning_7days(
    to_email: str,
    customer_name: str,
    plan_name: str,
    expiry_date: str
) -> bool:
    """Send 7-day expiry warning email"""
    subject = "⚠️ Your Subscription Expires in 7 Days"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 0; }}
            .header {{ background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); color: white; padding: 40px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .content {{ background: #f9f9f9; padding: 30px 20px; }}
            .warning-box {{ background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f59e0b; }}
            .button {{ background: #667eea; color: white; padding: 14px 35px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 20px 0; font-weight: bold; }}
            .button:hover {{ background: #5568d3; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; background: #e9e9e9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Subscription Expiring Soon</h1>
            </div>
            
            <div class="content">
                <p>Hi <strong>{customer_name}</strong>,</p>
                
                <div class="warning-box">
                    <p style="margin: 0; font-size: 16px;"><strong>⏰ Your {plan_name} subscription will expire in 7 days</strong></p>
                    <p style="margin: 10px 0 0 0;">Expiration Date: <strong>{expiry_date}</strong></p>
                </div>
                
                <p>To ensure uninterrupted access to all premium features, please renew your subscription before it expires.</p>
                
                <p><strong>What happens if you don't renew:</strong></p>
                <ul>
                    <li>🚫 Loss of access to premium features</li>
                    <li>🚫 Unable to use advanced AI capabilities</li>
                    <li>🚫 Limited customer support</li>
                </ul>
                
                <div style="text-align: center;">
                    <a href="{FRONTEND_URL}/landing" class="button">Renew Subscription Now</a>
                </div>
                
                <p style="margin-top: 30px;">If you have any questions or concerns, our support team is here to help!</p>
                
                <p style="margin-top: 20px;">Best regards,<br><strong>AI Assistant Team</strong></p>
            </div>
            
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def send_subscription_expiry_warning_1day(
    to_email: str,
    customer_name: str,
    plan_name: str,
    expiry_date: str
) -> bool:
    """Send 1-day expiry warning email"""
    subject = "🚨 URGENT: Your Subscription Expires Tomorrow!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 0; }}
            .header {{ background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); color: white; padding: 40px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .content {{ background: #f9f9f9; padding: 30px 20px; }}
            .urgent-box {{ background: #fee2e2; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #dc2626; }}
            .button {{ background: #dc2626; color: white; padding: 14px 35px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 20px 0; font-weight: bold; font-size: 16px; }}
            .button:hover {{ background: #b91c1c; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; background: #e9e9e9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚨 URGENT: Expires Tomorrow!</h1>
            </div>
            
            <div class="content">
                <p>Hi <strong>{customer_name}</strong>,</p>
                
                <div class="urgent-box">
                    <p style="margin: 0; font-size: 18px; font-weight: bold;">⏰ Your {plan_name} subscription expires TOMORROW!</p>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">Expiration Date: <strong>{expiry_date}</strong></p>
                </div>
                
                <p style="font-size: 16px;"><strong>This is your final reminder!</strong></p>
                
                <p>After tomorrow, you will lose access to:</p>
                <ul>
                    <li>❌ All premium features</li>
                    <li>❌ Advanced AI capabilities</li>
                    <li>❌ Priority support</li>
                    <li>❌ Custom integrations</li>
                </ul>
                
                <p style="font-size: 16px; font-weight: bold; color: #dc2626;">Act now to maintain uninterrupted service!</p>
                
                <div style="text-align: center;">
                    <a href="{FRONTEND_URL}/landing" class="button">RENEW NOW - Don't Lose Access!</a>
                </div>
                
                <p style="margin-top: 30px;">Need help? Contact our support team immediately for assistance with renewal.</p>
                
                <p style="margin-top: 20px;">Best regards,<br><strong>AI Assistant Team</strong></p>
            </div>
            
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def send_subscription_expired_email(
    to_email: str,
    customer_name: str,
    plan_name: str,
    expiry_date: str
) -> bool:
    """Send subscription expired notification"""
    subject = "Your Subscription Has Expired"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 0; }}
            .header {{ background: #6b7280; color: white; padding: 40px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .content {{ background: #f9f9f9; padding: 30px 20px; }}
            .info-box {{ background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .button {{ background: #667eea; color: white; padding: 14px 35px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 20px 0; font-weight: bold; }}
            .button:hover {{ background: #5568d3; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; background: #e9e9e9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Subscription Expired</h1>
            </div>
            
            <div class="content">
                <p>Hi <strong>{customer_name}</strong>,</p>
                
                <div class="info-box">
                    <p style="margin: 0;">Your {plan_name} subscription expired on <strong>{expiry_date}</strong></p>
                </div>
                
                <p>We hope you enjoyed using our AI Assistant premium features!</p>
                
                <p>Your account has been downgraded to the free tier. You can reactivate your premium subscription at any time to regain access to:</p>
                <ul>
                    <li>✨ Advanced AI capabilities</li>
                    <li>✨ Priority support</li>
                    <li>✨ Custom integrations</li>
                    <li>✨ Advanced analytics</li>
                </ul>
                
                <div style="text-align: center;">
                    <a href="{FRONTEND_URL}/landing" class="button">Reactivate Subscription</a>
                </div>
                
                <p style="margin-top: 30px;">Thank you for being part of our community. We'd love to have you back!</p>
                
                <p style="margin-top: 20px;">Best regards,<br><strong>AI Assistant Team</strong></p>
            </div>
            
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)
