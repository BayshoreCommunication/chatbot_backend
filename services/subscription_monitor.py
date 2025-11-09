"""
Subscription Monitoring Scheduler
Automatically checks subscription expiry dates and sends reminder emails
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import logging
from services.database import db
from services.subscription_emails import (
    send_subscription_expiry_warning_7days,
    send_subscription_expiry_warning_1day,
    send_subscription_expired_email
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_subscription_expiry():
    """
    Check all active subscriptions and send reminder emails
    - 7 days before expiry
    - 1 day before expiry
    - On expiry day
    """
    try:
        logger.info("Starting subscription expiry check...")
        
        now = datetime.utcnow()
        seven_days_from_now = now + timedelta(days=7)
        one_day_from_now = now + timedelta(days=1)
        
        # Get all users with active paid subscriptions
        users_collection = db.users
        active_users = users_collection.find({
            "has_paid_subscription": True,
            "subscription_end_date": {"$exists": True, "$ne": None}
        })
        
        emails_sent = {
            "7_day_warnings": 0,
            "1_day_warnings": 0,
            "expired_notifications": 0,
            "errors": 0
        }
        
        for user in active_users:
            try:
                user_email = user.get("email")
                user_name = user.get("organization_name") or user.get("email", "").split("@")[0]
                subscription_end = user.get("subscription_end_date")
                subscription_type = user.get("subscription_type", "Unknown Plan")
                last_reminder = user.get("last_reminder_sent")
                
                # Convert subscription_end to datetime if it's a string
                if isinstance(subscription_end, str):
                    subscription_end = datetime.fromisoformat(subscription_end.replace('Z', '+00:00'))
                
                # Calculate days until expiry
                days_until_expiry = (subscription_end - now).days
                
                logger.info(f"Checking user {user_email}: {days_until_expiry} days until expiry")
                
                # Check if subscription has expired
                if subscription_end <= now:
                    logger.info(f"Subscription expired for {user_email}")
                    # Update user subscription status
                    users_collection.update_one(
                        {"_id": user["_id"]},
                        {
                            "$set": {
                                "has_paid_subscription": False,
                                "subscription_type": "free",
                                "updated_at": now
                            }
                        }
                    )
                    
                    # Send expired notification
                    if send_subscription_expired_email(
                        user_email,
                        user_name,
                        subscription_type,
                        subscription_end.strftime("%B %d, %Y")
                    ):
                        emails_sent["expired_notifications"] += 1
                    
                    continue
                
                # 7-day warning (send once)
                if 6 <= days_until_expiry <= 7:
                    # Check if we already sent 7-day reminder
                    if last_reminder:
                        if isinstance(last_reminder, str):
                            last_reminder = datetime.fromisoformat(last_reminder.replace('Z', '+00:00'))
                        
                        # Don't send if we sent a reminder in the last 6 days
                        if (now - last_reminder).days < 6:
                            logger.info(f"7-day reminder already sent to {user_email}")
                            continue
                    
                    logger.info(f"Sending 7-day warning to {user_email}")
                    if send_subscription_expiry_warning_7days(
                        user_email,
                        user_name,
                        subscription_type,
                        subscription_end.strftime("%B %d, %Y")
                    ):
                        # Update last reminder sent
                        users_collection.update_one(
                            {"_id": user["_id"]},
                            {"$set": {"last_reminder_sent": now}}
                        )
                        emails_sent["7_day_warnings"] += 1
                
                # 1-day warning (send once)
                elif days_until_expiry == 1:
                    # Check if we already sent 1-day reminder today
                    if last_reminder:
                        if isinstance(last_reminder, str):
                            last_reminder = datetime.fromisoformat(last_reminder.replace('Z', '+00:00'))
                        
                        # Don't send if we sent a reminder in the last 12 hours
                        if (now - last_reminder).total_seconds() < 43200:  # 12 hours
                            logger.info(f"1-day reminder already sent to {user_email}")
                            continue
                    
                    logger.info(f"Sending 1-day warning to {user_email}")
                    if send_subscription_expiry_warning_1day(
                        user_email,
                        user_name,
                        subscription_type,
                        subscription_end.strftime("%B %d, %Y")
                    ):
                        # Update last reminder sent
                        users_collection.update_one(
                            {"_id": user["_id"]},
                            {"$set": {"last_reminder_sent": now}}
                        )
                        emails_sent["1_day_warnings"] += 1
                        
            except Exception as e:
                logger.error(f"Error processing user {user.get('email', 'unknown')}: {str(e)}")
                emails_sent["errors"] += 1
                continue
        
        logger.info(f"Subscription check completed: {emails_sent}")
        return emails_sent
        
    except Exception as e:
        logger.error(f"Error in subscription expiry check: {str(e)}")
        return {"error": str(e)}


async def subscription_monitor_loop():
    """
    Run subscription monitoring in a loop
    Checks every 12 hours
    """
    logger.info("Starting subscription monitor loop...")
    
    while True:
        try:
            # Run the expiry check
            result = await check_subscription_expiry()
            logger.info(f"Subscription check result: {result}")
            
            # Wait 12 hours before next check (43200 seconds)
            logger.info("Waiting 12 hours until next check...")
            await asyncio.sleep(43200)
            
        except Exception as e:
            logger.error(f"Error in subscription monitor loop: {str(e)}")
            # Wait 1 hour before retrying if there's an error
            await asyncio.sleep(3600)


def start_subscription_monitor():
    """
    Start the subscription monitoring service
    Call this function when the app starts
    """
    logger.info("Initializing subscription monitor...")
    
    # Create and run the monitoring loop in the background
    loop = asyncio.get_event_loop()
    loop.create_task(subscription_monitor_loop())
    
    logger.info("Subscription monitor started successfully")


if __name__ == "__main__":
    # For testing purposes
    asyncio.run(check_subscription_expiry())
