# 🎯 STRIPE PRODUCTION WEBHOOK SETUP GUIDE

# For: https://api.bayshorecommunication.org

============================================================
STEP-BY-STEP STRIPE DASHBOARD CONFIGURATION
============================================================

## YOUR BACKEND URL

https://api.bayshorecommunication.org

## WEBHOOK ENDPOINT URL

https://api.bayshorecommunication.org/payment/webhook

============================================================
PART 1: ADD WEBHOOK IN STRIPE DASHBOARD
============================================================

### Step 1: Login to Stripe Dashboard

1. Go to: https://dashboard.stripe.com/test/webhooks
2. Login with your Stripe account

### Step 2: Click "Add endpoint"

┌────────────────────────────────────────────────┐
│ Webhooks [+ Add endpoint]│ ← Click here
└────────────────────────────────────────────────┘

### Step 3: Configure Endpoint

**Endpoint URL:**
┌────────────────────────────────────────────────────────┐
│ https://api.bayshorecommunication.org/payment/webhook │
└────────────────────────────────────────────────────────┘

**Description (optional):**
Production webhook for subscription payments

**Version:**
Select latest API version (2024-11-20 or newer)

### Step 4: Select Events to Listen

Click "Select events" and choose these 6 events:

✅ checkout.session.completed
→ When customer completes payment

✅ customer.subscription.created
→ When new subscription is created

✅ customer.subscription.updated
→ When subscription is modified

✅ customer.subscription.deleted
→ When subscription is cancelled

✅ invoice.payment_succeeded
→ When recurring payment succeeds

✅ invoice.payment_failed
→ When payment fails

### Step 5: Click "Add endpoint"

### Step 6: Get Signing Secret

1. Click on the newly created endpoint
2. Find "Signing secret" section
3. Click "Reveal"
4. Copy the secret (starts with whsec\_)

Example: whsec_1A2B3C4D5E6F7G8H9I0J...

============================================================
PART 2: UPDATE YOUR .ENV FILE
============================================================

Current webhook secret in .env:
STRIPE_WEBHOOK_SECRET=whsec_VmLKNEW7wagzQLo5H8mQxCJMWAJQHUWq

⚠️ THIS IS WRONG! This is for LOCAL testing only.

✅ UPDATE TO:
STRIPE*WEBHOOK_SECRET=whsec*[YOUR_NEW_SECRET_FROM_STEP_6]

============================================================
PART 3: UPDATE BACKEND SERVER
============================================================

### If using Vercel/Railway/Heroku:

1. Go to your deployment platform
2. Add environment variable:
   Key: STRIPE*WEBHOOK_SECRET
   Value: whsec*[YOUR_SECRET]
3. Redeploy your backend

### If using Docker/VPS:

1. Update .env file on server
2. Restart containers:
   docker-compose down
   docker-compose up -d

============================================================
PART 4: TEST THE WEBHOOK
============================================================

### Method 1: Using Stripe Dashboard

1. Go to: https://dashboard.stripe.com/test/webhooks
2. Click on your endpoint
3. Click "Send test webhook"
4. Select "checkout.session.completed"
5. Click "Send test webhook"

Expected Result:
✅ Status: 200 (Success)
✅ Response time: < 5 seconds

### Method 2: Make Test Payment

1. Go to your checkout page
2. Use test card: 4242 4242 4242 4242
3. Expiry: Any future date
4. CVC: Any 3 digits
5. ZIP: Any 5 digits
6. Complete payment

### Method 3: Using Stripe CLI

stripe trigger checkout.session.completed \
 --override checkout_session:customer_email=test@example.com

============================================================
PART 5: VERIFY IT'S WORKING
============================================================

### Check 1: Stripe Dashboard

1. Go to: https://dashboard.stripe.com/test/webhooks
2. Click on your endpoint
3. Look at "Recent events"
4. You should see events with status "Succeeded"

### Check 2: Backend Logs

Check your backend logs for:
✅ "Received webhook event: checkout.session.completed"
✅ "Processing checkout completion for session: cs_test_xxxxx"
✅ "✅ Confirmation email sent successfully"

### Check 3: Database

Run this query to check subscription data:

```python
from services.database import db
users = list(db.users.find({'has_paid_subscription': True}))
for user in users:
    print(f"User: {user.get('email')}")
    print(f"  Subscription Type: {user.get('subscription_type')}")
    print(f"  Stripe ID: {user.get('stripe_subscription_id')}")
```

### Check 4: Customer Receives Email

Confirmation email should be sent to customer's email

============================================================
TROUBLESHOOTING
============================================================

### Issue: "Webhook signature verification failed"

**Cause:** Wrong STRIPE_WEBHOOK_SECRET
**Fix:**

1. Get secret from Stripe Dashboard
2. Update .env file
3. Restart backend server

### Issue: "404 Not Found"

**Cause:** Wrong webhook URL
**Fix:**

1. Check URL is: https://api.bayshorecommunication.org/payment/webhook
2. Make sure /payment/webhook endpoint exists
3. Check backend is deployed and running

### Issue: "500 Internal Server Error"

**Cause:** Backend error
**Fix:**

1. Check backend logs for errors
2. Verify all environment variables are set
3. Check MongoDB connection
4. Check SMTP credentials

### Issue: Payment succeeds but no subscription data

**Cause:** Webhook not firing or failing
**Fix:**

1. Check webhook is added in Stripe Dashboard
2. Verify webhook secret is correct
3. Check backend logs for webhook events
4. Make sure backend is publicly accessible

### Issue: Shows $0 in Stripe

**Cause:** Using test mode prices
**Fix:**

1. Verify you're using correct Price IDs in frontend
2. Check Stripe Dashboard → Products → Prices
3. Make sure prices are active and not archived

============================================================
STRIPE DASHBOARD CHECKLIST
============================================================

✅ Webhook endpoint added
✅ URL: https://api.bayshorecommunication.org/payment/webhook
✅ 6 events selected (checkout, subscription, invoice)
✅ Signing secret copied
✅ Webhook status: Enabled
✅ Test event sent successfully
✅ Recent events show "Succeeded" status

============================================================
BACKEND CHECKLIST
============================================================

✅ STRIPE_SECRET_KEY set in .env
✅ STRIPE_WEBHOOK_SECRET set in .env (production secret)
✅ Backend deployed and accessible
✅ /payment/webhook endpoint responds
✅ MongoDB connected
✅ SMTP configured for emails
✅ Backend logs showing webhook events

============================================================
FRONTEND CHECKLIST
============================================================

✅ Using correct Stripe Price IDs
✅ customerEmail passed to checkout session
✅ organizationId passed in metadata
✅ Success URL configured
✅ Cancel URL configured

============================================================
CURRENT CONFIGURATION
============================================================

Backend URL: https://api.bayshorecommunication.org
Webhook Endpoint: https://api.bayshorecommunication.org/payment/webhook
Webhook Secret: whsec_VmLKNEW7wagzQLo5H8mQxCJMWAJQHUWq (⚠️ UPDATE THIS!)

Frontend URL: https://chatbot-user-dashboard.vercel.app
SMTP Email: bayshoreai@gmail.com

Stripe Keys in .env:

- PUBLISHABLE_KEY: pk_test_51RymVQFS3P7wS29b...
- STRIPE_SECRET_KEY: sk_test_51RymVQFS3P7wS29b...

============================================================
NEXT STEPS
============================================================

1. ✅ Add webhook in Stripe Dashboard
   URL: https://api.bayshorecommunication.org/payment/webhook

2. ✅ Copy signing secret from Stripe Dashboard

3. ✅ Update .env with new STRIPE_WEBHOOK_SECRET

4. ✅ Redeploy backend with updated secret

5. ✅ Test payment with card 4242 4242 4242 4242

6. ✅ Verify webhook events in Stripe Dashboard

7. ✅ Check database for subscription data

8. ✅ Confirm customer receives email

============================================================
QUICK REFERENCE URLS
============================================================

Stripe Webhooks Dashboard:
https://dashboard.stripe.com/test/webhooks

Stripe Products & Prices:
https://dashboard.stripe.com/test/products

Stripe Customers:
https://dashboard.stripe.com/test/customers

Stripe Subscriptions:
https://dashboard.stripe.com/test/subscriptions

Your Backend API:
https://api.bayshorecommunication.org

Your Backend Docs:
https://api.bayshorecommunication.org/docs

Webhook Test Endpoint:
https://api.bayshorecommunication.org/payment/webhook

============================================================

Need help? Check the webhook logs in Stripe Dashboard!
