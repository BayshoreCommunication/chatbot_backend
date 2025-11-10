from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
import stripe
import os
from dotenv import load_dotenv
from services.auth import update_user
from services.database import (
    get_user_by_email,
    get_organization_by_user_id,
    update_organization_subscription,
    create_subscription,
    get_subscription_by_stripe_id,
    get_user_subscription,
    db
)
from datetime import datetime, timedelta
from models.organization import Subscription
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from services.subscription_emails import send_subscription_confirmation_email

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_51QCEQyP8UcLxbKnCosBh1PeLlk7yKSNtkoaERiMTqfJDKZLPXekSzsQaXZ3099U9EWHZT5DjJt97QXmT52TlAu4U00CJoNvgCt")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Email configuration
SMTP_SERVICE = os.getenv("SMPT_SERVICE", "gmail")
SMTP_HOST = os.getenv("SMPT_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMPT_PORT", "465"))
SMTP_MAIL = os.getenv("SMPT_MAIL", "bayshoreai@gmail.com")
SMTP_PASSWORD = os.getenv("SMPT_PASSWORD", "rcwasfkrlkvshxbd")  # Fixed: removed spaces

router = APIRouter()

# Email sending function
def send_email(to_email: str, subject: str, html_content: str):
    """Send email using SMTP"""
    try:
        # Validate email configuration
        if not SMTP_PASSWORD or not SMTP_MAIL:
            logger.error("SMTP configuration incomplete: Missing password or email")
            return False
            
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_MAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        logger.info(f"Attempting to send email to {to_email}")
        logger.info(f"SMTP Host: {SMTP_HOST}, Port: {SMTP_PORT}")
        
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_MAIL, SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"✅ Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ SMTP Authentication failed: {str(e)}")
        logger.error(f"Check SMTP_MAIL and SMTP_PASSWORD in .env file")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ SMTP error when sending to {to_email}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        return False

# Email templates
def get_payment_confirmation_email(customer_name: str, plan_name: str, amount: float, billing_cycle: str, next_billing_date: str):
    """Payment confirmation email template"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .details {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Payment Successful!</h1>
            </div>
            <div class="content">
                <p>Hi {customer_name},</p>
                <p>Thank you for subscribing to our AI Assistant! Your payment has been processed successfully.</p>
                
                <div class="details">
                    <h3>Subscription Details:</h3>
                    <p><strong>Plan:</strong> {plan_name}</p>
                    <p><strong>Amount:</strong> ${amount:.2f}</p>
                    <p><strong>Billing Cycle:</strong> {billing_cycle}</p>
                    <p><strong>Next Billing Date:</strong> {next_billing_date}</p>
                </div>
                
                <p>You can now access all premium features of your subscription.</p>
                
                <a href="{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/dashboard" class="button">Go to Dashboard</a>
                
                <p>If you have any questions, feel free to reach out to our support team.</p>
                
                <p>Best regards,<br>AI Assistant Team</p>
            </div>
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_subscription_expiry_warning_email(customer_name: str, plan_name: str, days_remaining: int, renewal_date: str, amount: float):
    """Subscription expiry warning email template"""
    urgency = "⚠️ URGENT:" if days_remaining == 1 else "⏰ Reminder:"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .warning-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
            .button {{ background: #f5576c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{urgency} Subscription Renewal</h1>
            </div>
            <div class="content">
                <p>Hi {customer_name},</p>
                
                <div class="warning-box">
                    <h3>Your subscription is expiring soon!</h3>
                    <p><strong>Plan:</strong> {plan_name}</p>
                    <p><strong>Days Remaining:</strong> {days_remaining} day{"s" if days_remaining > 1 else ""}</p>
                    <p><strong>Renewal Date:</strong> {renewal_date}</p>
                    <p><strong>Renewal Amount:</strong> ${amount:.2f}</p>
                </div>
                
                <p>Your subscription will automatically renew on <strong>{renewal_date}</strong> unless you cancel before then.</p>
                
                <p>To manage your subscription or update payment methods:</p>
                
                <a href="{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/dashboard/billing" class="button">Manage Subscription</a>
                
                <p>Thank you for being a valued customer!</p>
                
                <p>Best regards,<br>AI Assistant Team</p>
            </div>
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

def get_subscription_cancelled_email(customer_name: str, plan_name: str, end_date: str):
    """Subscription cancelled email template"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .info-box {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #667eea; }}
            .button {{ background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Subscription Cancelled</h1>
            </div>
            <div class="content">
                <p>Hi {customer_name},</p>
                <p>We're sorry to see you go. Your subscription has been cancelled.</p>
                
                <div class="info-box">
                    <h3>Cancellation Details:</h3>
                    <p><strong>Plan:</strong> {plan_name}</p>
                    <p><strong>Access Until:</strong> {end_date}</p>
                </div>
                
                <p>You will continue to have access to all premium features until <strong>{end_date}</strong>.</p>
                
                <p>We'd love to have you back! If you change your mind:</p>
                
                <a href="{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/landing" class="button">Resubscribe Now</a>
                
                <p>If you have any feedback or questions, please don't hesitate to reach out.</p>
                
                <p>Best regards,<br>AI Assistant Team</p>
            </div>
            <div class="footer">
                <p>© 2025 AI Assistant. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

class CheckoutSessionRequest(BaseModel):
    priceId: str
    successUrl: str
    cancelUrl: str
    customerEmail: str = None
    planId: str
    billingCycle: str  # 'monthly' or 'yearly'
    organizationId: str

class VerifySessionRequest(BaseModel):
    sessionId: str

@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutSessionRequest):
    """Create a Stripe checkout session for subscription payment"""
    try:
        logger.info(f"Creating checkout session for plan: {request.planId}, cycle: {request.billingCycle}")
        
        # Free trial validation - check if user already used their free trial
        if request.planId == 'trial' and request.customerEmail:
            user = get_user_by_email(request.customerEmail)
            if user and user.get('free_trial_used', False):
                raise HTTPException(
                    status_code=400,
                    detail="You have already used your free trial. Please select a paid plan."
                )
        
        # Use the actual Stripe Price IDs from the frontend
        session_params = {
            'payment_method_types': ['card'],
            'line_items': [{
                'price': request.priceId,  # Use the actual Stripe Price ID
                'quantity': 1,
            }],
            'mode': 'subscription',
            'success_url': request.successUrl + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': request.cancelUrl,
            'customer_email': request.customerEmail,
            'allow_promotion_codes': True,
            'metadata': {
                'organization_id': request.organizationId,
                'plan_id': request.planId,
                'billing_cycle': request.billingCycle
            },
            'subscription_data': {
                'metadata': {
                    'organization_id': request.organizationId,
                    'plan_id': request.planId,
                    'billing_cycle': request.billingCycle
                }
            }
        }

        # Add trial period for trial plan
        if request.planId == 'trial':
            session_params['subscription_data']['trial_period_days'] = 30
        
        session = stripe.checkout.Session.create(**session_params)
        
        logger.info(f"Session created successfully: {session.id}")
        return {"sessionId": session.id}
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"General error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/verify-session")
async def verify_session(request: VerifySessionRequest):
    """Verify a completed Stripe checkout session"""
    try:
        print(f"Starting verify_session with sessionId: {request.sessionId}")
        
        # Retrieve the session
        session = stripe.checkout.Session.retrieve(request.sessionId)
        print(f"Session payment status: {session.payment_status}")
        
        if session.payment_status == 'paid':
            # Get subscription details from Stripe
            subscription = stripe.Subscription.retrieve(session.subscription)
            print(f"Subscription ID: {subscription.id}")
            
            # Get organization ID from session metadata
            organization_id = session.metadata.get('organization_id')
            if not organization_id:
                raise HTTPException(status_code=400, detail="No organization ID found in session metadata")
            
            # Check if subscription already exists in database
            existing_subscription = get_subscription_by_stripe_id(subscription.id)
            if existing_subscription:
                print(f"Subscription already exists in database: {existing_subscription}")
                return {
                    "success": True,
                    "subscriptionId": subscription.id,
                    "customerEmail": session.customer_details.email,
                    "message": "Payment already verified"
                }
            
            # Get customer email
            customer_email = session.customer_details.email
            print(f"Customer email: {customer_email}")
            
            # Get price information from the subscription's first item
            items = stripe.SubscriptionItem.list(subscription=subscription.id)
            print(f"Found {len(items.data)} subscription items")
            
            if not items.data:
                raise HTTPException(status_code=400, detail="No subscription items found")
            
            # Get the first item
            first_item = items.data[0]
            print(f"First subscription item ID: {first_item.id}")
            
            # Get price information
            price = first_item.price
            payment_amount = price.unit_amount / 100  # Convert cents to dollars
            subscription_tier = price.nickname or "professional"
            print(f"Payment amount: ${payment_amount}")
            print(f"Subscription tier: {subscription_tier}")
            
            # Get user by email
            user = get_user_by_email(customer_email)
            print(f"Found user: {user}")
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Update user subscription status
            update_user(user["id"], {
                "has_paid_subscription": True,
                "subscription_id": subscription.id
            })
            print(f"Updated user subscription status")
            
            # Update organization subscription
            update_organization_subscription(organization_id, subscription.id)
            print(f"Updated organization subscription")
            
            # Create subscription record
            subscription_data = {
                "user_id": user["id"],
                "organization_id": organization_id,
                "stripe_subscription_id": subscription.id,
                "payment_amount": payment_amount,
                "subscription_tier": subscription_tier,
                "current_period_start": datetime.fromtimestamp(first_item.current_period_start),
                "current_period_end": datetime.fromtimestamp(first_item.current_period_end)
            }
            print(f"Prepared subscription data: {subscription_data}")
            
            # Create subscription in database
            created_subscription = create_subscription(**subscription_data)
            print(f"Created subscription in database: {created_subscription}")
            
            return {
                "success": True,
                "subscriptionId": subscription.id,
                "customerEmail": customer_email,
                "message": "Payment verified successfully"
            }
        else:
            print(f"Payment not completed. Status: {session.payment_status}")
            return {
                "success": False,
                "message": "Payment not completed"
            }
    
    except stripe.error.StripeError as e:
        print(f"Stripe error in verify_session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error in verify_session: {str(e)}")
        print(f"Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-portal-session")
async def create_portal_session(customer_id: str, return_url: str):
    """Create a Stripe customer portal session for subscription management"""
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        
        return {"url": session.url}
    
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/subscription/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details"""
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "plan": {
                "id": subscription.items.data[0].price.id,
                "amount": subscription.items.data[0].price.unit_amount,
                "currency": subscription.items.data[0].price.currency,
                "interval": subscription.items.data[0].price.recurring.interval,
            }
        }
    
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/user-subscription/{user_id}")
async def get_user_subscription_data(user_id: str):
    """Get the most recent subscription data for a specific user"""
    try:
        print(f"Fetching most recent subscription for user: {user_id}")
        
        # Direct MongoDB query with sorting by created_at in descending order
        subscription = db.subscriptions.find_one(
            {"user_id": user_id},
            sort=[("created_at", -1)]  # Sort by created_at in descending order
        )
        print(f"Found subscription: {subscription}")
        
        if not subscription:
            print(f"No subscription found for user: {user_id}")
            raise HTTPException(status_code=404, detail=f"No subscription found for user: {user_id}")
        
        # Convert ObjectId to string
        subscription["_id"] = str(subscription["_id"])
        
        return {
            "status": "success",
            "data": subscription
        }
    except Exception as e:
        print(f"Error fetching subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Handle Stripe webhook events"""
    try:
        payload = await request.body()
        
        # Verify webhook signature if secret is configured
        if STRIPE_WEBHOOK_SECRET:
            try:
                event = stripe.Webhook.construct_event(
                    payload, stripe_signature, STRIPE_WEBHOOK_SECRET
                )
            except ValueError as e:
                logger.error(f"Invalid payload: {e}")
                raise HTTPException(status_code=400, detail="Invalid payload")
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"Invalid signature: {e}")
                raise HTTPException(status_code=400, detail="Invalid signature")
        else:
            event = stripe.Event.construct_from(
                stripe.util.convert_to_dict(payload), stripe.api_key
            )
        
        logger.info(f"Received webhook event: {event['type']}")
        
        # Handle different event types
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            await handle_checkout_completed(session)
            
        elif event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            await handle_subscription_created(subscription)
            
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            await handle_subscription_updated(subscription)
            
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            await handle_subscription_deleted(subscription)
            
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            await handle_payment_succeeded(invoice)
            
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            await handle_payment_failed(invoice)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_checkout_completed(session):
    """Handle successful checkout"""
    try:
        logger.info(f"Processing checkout completion for session: {session['id']}")
        
        customer_email = session.get('customer_details', {}).get('email')
        subscription_id = session.get('subscription')
        
        if not customer_email or not subscription_id:
            logger.error("Missing customer email or subscription ID")
            return
        
        # Get user
        user = get_user_by_email(customer_email)
        if not user:
            logger.error(f"User not found: {customer_email}")
            return
        
        # Get subscription details from Stripe
        subscription = stripe.Subscription.retrieve(subscription_id)
        organization_id = session.get('metadata', {}).get('organization_id')
        plan_id = session.get('metadata', {}).get('plan_id', 'professional')
        billing_cycle = session.get('metadata', {}).get('billing_cycle', 'monthly')
        
        # Calculate subscription dates
        subscription_start = datetime.fromtimestamp(subscription['current_period_start'])
        subscription_end = datetime.fromtimestamp(subscription['current_period_end'])
        
        # Get price information
        amount = subscription['items']['data'][0]['price']['unit_amount'] / 100
        plan_name = f"{plan_id.capitalize()}"
        
        # Determine subscription type based on plan_id
        if plan_id == 'trial':
            subscription_type = 'free_trial'
        elif plan_id == 'professional':
            subscription_type = 'professional'
        elif plan_id == 'enterprise':
            subscription_type = 'enterprise'
        else:
            subscription_type = 'free'
        
        # Prepare update data
        update_data = {
            "has_paid_subscription": True,
            "subscription_type": subscription_type,
            "subscription_start_date": subscription_start,
            "subscription_end_date": subscription_end,
            "billing_cycle": billing_cycle,
            "stripe_subscription_id": subscription_id,
            "stripe_customer_id": subscription['customer'],
            "updated_at": datetime.utcnow()
        }
        
        # Mark free trial as used if this is a trial subscription
        if plan_id == 'trial':
            update_data["free_trial_used"] = True
            logger.info(f"Marking free trial as used for {customer_email}")
        
        # Update user subscription data with all new fields
        update_user(user["id"], update_data)
        
        # Update organization if exists
        if organization_id:
            update_organization_subscription(organization_id, subscription_id)
        
        # Send subscription confirmation email using the proper service function
        customer_name = user.get('organization_name') or user.get('email', '').split('@')[0]
        
        logger.info(f"Sending confirmation email to {customer_email}")
        email_sent = send_subscription_confirmation_email(
            to_email=customer_email,
            customer_name=customer_name,
            plan_name=plan_name,
            amount=amount,
            billing_cycle=billing_cycle,
            subscription_start=subscription_start.strftime('%B %d, %Y'),
            subscription_end=subscription_end.strftime('%B %d, %Y')
        )
        
        if email_sent:
            logger.info(f"✅ Confirmation email sent successfully to {customer_email}")
        else:
            logger.error(f"❌ Failed to send confirmation email to {customer_email}")
        
        logger.info(f"Checkout completed successfully for {customer_email}")
        logger.info(f"Subscription dates: {subscription_start} to {subscription_end}")
        
    except Exception as e:
        logger.error(f"Error handling checkout completion: {str(e)}")

async def handle_subscription_created(subscription):
    """Handle subscription creation"""
    try:
        logger.info(f"Processing subscription creation: {subscription['id']}")
        
        customer = stripe.Customer.retrieve(subscription['customer'])
        customer_email = customer['email']
        
        # Get user
        user = get_user_by_email(customer_email)
        if not user:
            logger.error(f"User not found: {customer_email}")
            return
        
        # Calculate subscription dates
        subscription_start = datetime.fromtimestamp(subscription['current_period_start'])
        subscription_end = datetime.fromtimestamp(subscription['current_period_end'])
        plan_id = subscription.get('metadata', {}).get('plan_id', 'professional')
        billing_cycle = subscription.get('metadata', {}).get('billing_cycle', 'monthly')
        
        # Determine subscription type
        if plan_id == 'trial':
            subscription_type = 'free_trial'
        elif plan_id == 'professional':
            subscription_type = 'professional'
        elif plan_id == 'enterprise':
            subscription_type = 'enterprise'
        else:
            subscription_type = 'free'
        
        # Update user with subscription details
        update_user(user["id"], {
            "has_paid_subscription": True,
            "subscription_type": subscription_type,
            "subscription_start_date": subscription_start,
            "subscription_end_date": subscription_end,
            "billing_cycle": billing_cycle,
            "stripe_subscription_id": subscription['id'],
            "stripe_customer_id": subscription['customer'],
            "updated_at": datetime.utcnow()
        })
        
        # Create subscription record in database
        subscription_data = {
            "user_id": user["id"],
            "organization_id": subscription.get('metadata', {}).get('organization_id'),
            "stripe_subscription_id": subscription['id'],
            "payment_amount": subscription['items']['data'][0]['price']['unit_amount'] / 100,
            "subscription_tier": subscription_type,
            "current_period_start": subscription_start,
            "current_period_end": subscription_end
        }
        
        create_subscription(**subscription_data)
        logger.info(f"Subscription created in database for {customer_email}")
        logger.info(f"Subscription period: {subscription_start} to {subscription_end}")
        
    except Exception as e:
        logger.error(f"Error handling subscription creation: {str(e)}")

async def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        logger.info(f"Processing subscription update: {subscription['id']}")
        
        # Check if subscription is about to expire
        current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
        days_until_renewal = (current_period_end - datetime.now()).days
        
        # Send warning emails
        if days_until_renewal == 7 or days_until_renewal == 1:
            customer = stripe.Customer.retrieve(subscription['customer'])
            customer_email = customer['email']
            user = get_user_by_email(customer_email)
            
            if user:
                plan_name = subscription.get('metadata', {}).get('plan_id', 'Professional').capitalize()
                amount = subscription['items']['data'][0]['price']['unit_amount'] / 100
                
                send_email(
                    to_email=customer_email,
                    subject=f"⏰ Subscription Renewal in {days_until_renewal} day{'s' if days_until_renewal > 1 else ''}",
                    html_content=get_subscription_expiry_warning_email(
                        customer_name=user.get('name', 'Valued Customer'),
                        plan_name=plan_name,
                        days_remaining=days_until_renewal,
                        renewal_date=current_period_end.strftime('%B %d, %Y'),
                        amount=amount
                    )
                )
        
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")

async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        logger.info(f"Processing subscription deletion: {subscription['id']}")
        
        customer = stripe.Customer.retrieve(subscription['customer'])
        customer_email = customer['email']
        user = get_user_by_email(customer_email)
        
        if user:
            # Update user subscription status - reset to free tier
            update_user(user["id"], {
                "has_paid_subscription": False,
                "subscription_type": "free",
                "stripe_subscription_id": None,
                "billing_cycle": None,
                "updated_at": datetime.utcnow()
                # Note: We keep subscription_start_date and subscription_end_date for history
            })
            
            # Send cancellation email
            plan_name = subscription.get('metadata', {}).get('plan_id', 'Professional').capitalize()
            end_date = datetime.fromtimestamp(subscription['current_period_end']).strftime('%B %d, %Y')
            
            send_email(
                to_email=customer_email,
                subject="Subscription Cancelled - We're Sorry to See You Go",
                html_content=get_subscription_cancelled_email(
                    customer_name=user.get('organization_name') or user.get('email', '').split('@')[0],
                    plan_name=plan_name,
                    end_date=end_date
                )
            )
            
        logger.info(f"Subscription deleted successfully for {customer_email}")
        
    except Exception as e:
        logger.error(f"Error handling subscription deletion: {str(e)}")

async def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    try:
        logger.info(f"Processing successful payment for invoice: {invoice['id']}")
        
        customer = stripe.Customer.retrieve(invoice['customer'])
        customer_email = customer['email']
        
        # For recurring payments (not first payment)
        if invoice.get('billing_reason') == 'subscription_cycle':
            user = get_user_by_email(customer_email)
            if user:
                amount = invoice['amount_paid'] / 100
                subscription = stripe.Subscription.retrieve(invoice['subscription'])
                plan_name = subscription.get('metadata', {}).get('plan_id', 'Professional').capitalize()
                next_billing = datetime.fromtimestamp(subscription['current_period_end']).strftime('%B %d, %Y')
                billing_cycle = subscription.get('metadata', {}).get('billing_cycle', 'monthly')
                
                send_email(
                    to_email=customer_email,
                    subject="✅ Payment Received - Subscription Renewed",
                    html_content=get_payment_confirmation_email(
                        customer_name=user.get('name', 'Valued Customer'),
                        plan_name=plan_name,
                        amount=amount,
                        billing_cycle=billing_cycle,
                        next_billing_date=next_billing
                    )
                )
        
    except Exception as e:
        logger.error(f"Error handling payment success: {str(e)}")

async def handle_payment_failed(invoice):
    """Handle failed payment"""
    try:
        logger.info(f"Processing failed payment for invoice: {invoice['id']}")
        
        customer = stripe.Customer.retrieve(invoice['customer'])
        customer_email = customer['email']
        user = get_user_by_email(customer_email)
        
        if user:
            # Send payment failed email
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .alert-box {{ background: #ffe6e6; border-left: 4px solid #f5576c; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                    .button {{ background: #f5576c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>⚠️ Payment Failed</h1>
                    </div>
                    <div class="content">
                        <p>Hi {user.get('name', 'Valued Customer')},</p>
                        
                        <div class="alert-box">
                            <h3>We were unable to process your payment</h3>
                            <p>Your subscription payment has failed. Please update your payment method to continue using our services.</p>
                        </div>
                        
                        <p>To avoid service interruption, please update your payment information as soon as possible.</p>
                        
                        <a href="{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/dashboard/billing" class="button">Update Payment Method</a>
                        
                        <p>If you have any questions, please contact our support team.</p>
                        
                        <p>Best regards,<br>AI Assistant Team</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            send_email(
                to_email=customer_email,
                subject="❌ Payment Failed - Action Required",
                html_content=html_content
            )
        
    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}") 