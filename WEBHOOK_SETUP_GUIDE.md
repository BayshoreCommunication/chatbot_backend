# Stripe Webhook Setup Guide

## Complete Payment System with Email Notifications

This guide will help you set up the complete payment system with Stripe webhooks and email notifications.

## Features Implemented

✅ **Payment Processing**

- Stripe Checkout integration
- Support for Monthly and Yearly subscriptions
- Trial period support (30 days)

✅ **Email Notifications**

- Payment confirmation emails
- Subscription renewal warnings (7 days and 1 day before)
- Subscription cancellation emails
- Payment failure alerts

✅ **Webhook Events Handled**

- `checkout.session.completed` - When payment is successful
- `customer.subscription.created` - When subscription is created
- `customer.subscription.updated` - When subscription is updated
- `customer.subscription.deleted` - When subscription is cancelled
- `invoice.payment_succeeded` - When recurring payment succeeds
- `invoice.payment_failed` - When payment fails

## Setup Instructions

### 1. Configure Environment Variables

Add these to your `.env` file:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_51QCEQyP8UcLxbKnCosBh1PeLlk7yKSNtkoaERiMTqfJDKZLPXekSzsQaXZ3099U9EWHZT5DjJt97QXmT52TlAu4U00CJoNvgCt
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# SMTP Email Configuration
SMPT_SERVICE=gmail
SMPT_HOST=smtp.gmail.com
SMPT_PORT=465
SMPT_MAIL=bayshoreai@gmail.com
SMPT_PASSWORD=rcwa sfkr lkvs hxbd

# Frontend URL (for email links)
FRONTEND_URL=https://your-domain.com
```

### 2. Install Required Python Packages

```bash
pip install stripe python-dotenv
```

### 3. Set Up Stripe Webhook

#### Option A: Production (with deployed backend)

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
2. Click "Add endpoint"
3. Enter your webhook URL: `https://your-api-domain.com/payment/webhook`
4. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Click "Add endpoint"
6. Copy the "Signing secret" (starts with `whsec_`)
7. Add it to your `.env` file as `STRIPE_WEBHOOK_SECRET`

#### Option B: Local Development (using Stripe CLI)

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli

2. Login to Stripe CLI:

```bash
stripe login
```

3. Forward webhooks to your local server:

```bash
stripe listen --forward-to http://localhost:8000/payment/webhook
```

4. Copy the webhook signing secret from the output
5. Add it to your `.env` file as `STRIPE_WEBHOOK_SECRET`

### 4. Configure Gmail SMTP (if using Gmail)

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a new app password
   - Use this password in `SMPT_PASSWORD`

**Note**: The password in the example `rcwa sfkr lkvs hxbd` should be replaced with spaces removed: `rcwasfkrlkvshxbd`

### 5. Test Your Setup

#### Test Stripe Payment:

1. Use test card: `4242 4242 4242 4242`
2. Any future expiry date
3. Any 3-digit CVC

#### Test Webhook Locally:

```bash
# Trigger a test event
stripe trigger checkout.session.completed
```

#### Test Email Sending:

```python
# Run this Python script to test email
from routes.payment import send_email, get_payment_confirmation_email

send_email(
    to_email="test@example.com",
    subject="Test Email",
    html_content=get_payment_confirmation_email(
        customer_name="Test User",
        plan_name="Professional - Monthly",
        amount=49.00,
        billing_cycle="monthly",
        next_billing_date="January 1, 2026"
    )
)
```

### 6. Webhook Event Flow

```
User Subscribes
    ↓
checkout.session.completed (Payment successful)
    ↓
Send Payment Confirmation Email
    ↓
customer.subscription.created
    ↓
Save subscription to database
    ↓
Subscription Active ✅

---

7 Days Before Renewal
    ↓
customer.subscription.updated
    ↓
Send Renewal Warning Email ⏰

---

1 Day Before Renewal
    ↓
customer.subscription.updated
    ↓
Send Urgent Renewal Warning Email ⚠️

---

Renewal Date
    ↓
invoice.payment_succeeded
    ↓
Send Payment Confirmation Email ✅
(OR)
invoice.payment_failed
    ↓
Send Payment Failed Email ❌

---

User Cancels
    ↓
customer.subscription.deleted
    ↓
Send Cancellation Email 👋
```

### 7. API Endpoint

**Webhook Endpoint:**

```
POST /payment/webhook
```

This endpoint automatically handles all Stripe webhook events.

### 8. Monitoring

Check webhook logs in:

- Stripe Dashboard → Developers → Webhooks → [Your endpoint] → Events
- Your server logs for email sending status

### 9. Troubleshooting

**Webhooks not receiving events:**

- Check webhook endpoint URL is correct
- Verify webhook secret matches
- Check firewall/security settings
- Look at Stripe Dashboard → Webhooks → Failed attempts

**Emails not sending:**

- Verify SMTP credentials
- Check email logs in server output
- Ensure app password is correct (no spaces)
- Check spam folder

**Subscription not updating:**

- Check database connection
- Verify organization_id is passed correctly
- Look at server logs for errors

### 10. Cron Job for Subscription Checks (Optional)

Create a cron job to check subscriptions daily:

```python
# Add to routes/payment.py

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

def check_expiring_subscriptions():
    """Check for subscriptions expiring soon"""
    try:
        # Get all active subscriptions
        subscriptions = db.subscriptions.find({})

        for sub in subscriptions:
            end_date = sub.get('current_period_end')
            if end_date:
                days_until = (end_date - datetime.now()).days

                # Send warnings at 7 days and 1 day
                if days_until == 7 or days_until == 1:
                    user = get_user_by_id(sub['user_id'])
                    if user:
                        send_email(
                            to_email=user['email'],
                            subject=f"⏰ Subscription Renewal in {days_until} days",
                            html_content=get_subscription_expiry_warning_email(...)
                        )
    except Exception as e:
        logger.error(f"Error checking subscriptions: {e}")

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_expiring_subscriptions, 'interval', hours=24)
scheduler.start()
```

## Email Templates

All email templates are HTML-formatted with:

- Responsive design
- Brand colors (blue/purple gradient)
- Clear call-to-action buttons
- Mobile-friendly layout

## Security Notes

1. **Never commit** `.env` file to git
2. Use environment variables for all secrets
3. Validate webhook signatures
4. Use HTTPS in production
5. Rotate API keys regularly

## Support

For issues or questions:

- Check server logs
- Review Stripe Dashboard
- Contact: bayshoreai@gmail.com

---

✅ Setup Complete! Your payment system with automated emails is ready! 🚀
