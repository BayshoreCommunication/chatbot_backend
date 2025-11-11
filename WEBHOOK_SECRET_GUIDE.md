# 🔑 How to Collect Webhook Secret Key - Visual Guide

## 📍 Where is the Secret?

There are **TWO different secrets** depending on your setup:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  LOCAL TESTING          vs          PRODUCTION              │
│  (Development)                      (Live Server)           │
│                                                             │
│  Stripe CLI             vs          Stripe Dashboard        │
│  whsec_xxxxx_local                 whsec_xxxxx_prod        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🖥️ METHOD 1: Local Testing (Stripe CLI)

### Visual Flow:

```
┌──────────────┐
│  Terminal    │
└──────┬───────┘
       │
       │ Run: stripe listen --forward-to http://localhost:8000/payment/webhook
       │
       ▼
┌────────────────────────────────────────────────────────────┐
│ > Ready! Your webhook signing secret is whsec_ABC123...   │ ◄── COPY THIS!
└────────────────────────────────────────────────────────────┘
       │
       │ Paste into .env
       ▼
┌────────────────────────────────────────────────────────────┐
│ STRIPE_WEBHOOK_SECRET=whsec_ABC123...                      │
└────────────────────────────────────────────────────────────┘
       │
       │ Restart backend
       ▼
    ✅ Done!
```

### Commands:

```cmd
# Step 1: Start listener
stripe listen --forward-to http://localhost:8000/payment/webhook

# You'll see this output:
> Ready! You are using Stripe API Version [2024-11-20.acacia].
  Your webhook signing secret is whsec_1a2b3c4d5e6f7g8h9i0j
  (^C to quit)

# Step 2: Copy the secret (everything after "secret is ")
whsec_1a2b3c4d5e6f7g8h9i0j

# Step 3: Update .env
# Open: d:\bayai-chatbot\chatbot_backend\.env
# Change line 28 from:
STRIPE_WEBHOOK_SECRET=whsec_VmLKNEW7wagzQLo5H8mQxCJMWAJQHUWq
# To:
STRIPE_WEBHOOK_SECRET=whsec_1a2b3c4d5e6f7g8h9i0j

# Step 4: Restart backend (Ctrl+C then run again)
python -m uvicorn main:app --reload --port 8000
```

---

## 🌐 METHOD 2: Production (Stripe Dashboard)

### Visual Flow:

```
┌──────────────────────────────────────────────────────────┐
│  1. Go to: https://dashboard.stripe.com/test/webhooks   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  2. Click "Add endpoint" button                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  3. Enter details:                                       │
│     URL: https://your-backend.vercel.app/payment/webhook│
│     Events: Select 6 events (see below)                 │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  4. Click on the created endpoint                        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  5. Click "Reveal" under "Signing secret"                │
│     whsec_PRODUCTION_SECRET_HERE                         │ ◄── COPY THIS!
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  6. Add to Vercel/Production environment variables       │
│     STRIPE_WEBHOOK_SECRET=whsec_PRODUCTION_SECRET_HERE   │
└──────────────────────────────────────────────────────────┘
```

### Screenshot Guide:

#### Step 1: Navigate to Webhooks

```
Stripe Dashboard → Developers → Webhooks
URL: https://dashboard.stripe.com/test/webhooks
```

#### Step 2: Click "Add endpoint"

```
┌─────────────────────────────────────────────────┐
│  Webhooks                         [Add endpoint]│ ◄── Click here
├─────────────────────────────────────────────────┤
│  No endpoints yet                               │
└─────────────────────────────────────────────────┘
```

#### Step 3: Configure Endpoint

```
┌──────────────────────────────────────────────────────────┐
│  Add endpoint                                            │
├──────────────────────────────────────────────────────────┤
│  Endpoint URL                                            │
│  ┌────────────────────────────────────────────────────┐ │
│  │ https://your-backend.vercel.app/payment/webhook    │ │ ◄── Your URL
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Events to send                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ ☑ checkout.session.completed                       │ │
│  │ ☑ customer.subscription.created                    │ │
│  │ ☑ customer.subscription.updated                    │ │
│  │ ☑ customer.subscription.deleted                    │ │
│  │ ☑ invoice.payment_succeeded                        │ │
│  │ ☑ invoice.payment_failed                           │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│                                   [Add endpoint]         │
└──────────────────────────────────────────────────────────┘
```

#### Step 4: Reveal Secret

```
┌──────────────────────────────────────────────────────────┐
│  Endpoint details                                        │
├──────────────────────────────────────────────────────────┤
│  Signing secret                              [Reveal]    │ ◄── Click here
│  whsec_••••••••••••••••••••••••••••••••                 │
│                                                          │
│  After clicking Reveal:                                  │
│  whsec_1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P              │ ◄── COPY THIS!
└──────────────────────────────────────────────────────────┘
```

---

## 🎯 Quick Reference Table

| Scenario          | Where to Get Secret            | Format        | Duration                                  |
| ----------------- | ------------------------------ | ------------- | ----------------------------------------- |
| **Local Testing** | `stripe listen` command output | `whsec_xxxxx` | Changes each time you run `stripe listen` |
| **Production**    | Stripe Dashboard → Webhooks    | `whsec_xxxxx` | Permanent until you revoke it             |

---

## 🔄 Complete Workflow

### For Local Development:

```bash
# Terminal 1: Start backend
cd d:\bayai-chatbot\chatbot_backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Start Stripe listener and GET SECRET
stripe listen --forward-to http://localhost:8000/payment/webhook
# Output shows: "Your webhook signing secret is whsec_ABC123..."

# Terminal 3: Update .env and restart backend
# 1. Copy the secret from Terminal 2
# 2. Update .env: STRIPE_WEBHOOK_SECRET=whsec_ABC123...
# 3. Go to Terminal 1, press Ctrl+C
# 4. Restart: python -m uvicorn main:app --reload --port 8000

# Terminal 2: Still running (keep it open)

# Terminal 3: Test
stripe trigger checkout.session.completed
```

---

## 🛠️ Helper Scripts

### Interactive Helper (EASIEST):

```cmd
get_webhook_secret.bat
```

This will guide you through the entire process!

### Quick Commands:

```cmd
# Just show me the secret
stripe listen --print-secret

# Start listener and show secret
stripe listen --forward-to http://localhost:8000/payment/webhook

# Check current .env
findstr "STRIPE_WEBHOOK_SECRET" .env
```

---

## ❓ FAQ

**Q: Do I need different secrets for test and live mode?**
A: Yes! You'll have separate secrets for test mode and live mode.

**Q: Can I use the same secret for local and production?**
A: No. Local uses CLI secret, production uses Dashboard secret.

**Q: How often does the CLI secret change?**
A: Every time you run `stripe listen`, you get a NEW secret.

**Q: What if I lose the production secret?**
A: You can reveal it anytime in the Dashboard, or create a new endpoint.

**Q: My webhook isn't working, what should I check?**
A:

1. Secret matches what's in .env ✅
2. Backend was restarted after updating .env ✅
3. Stripe listener is running (for local) ✅
4. Endpoint URL is correct (for production) ✅

---

## 🎉 Success Indicators

When you have the correct secret, you'll see:

**Backend logs:**

```
INFO: Received webhook event: checkout.session.completed
INFO: ✅ Confirmation email sent successfully
```

**Stripe CLI logs:**

```
2025-01-18 10:30:45   --> checkout.session.completed [evt_xxxxx]
2025-01-18 10:30:45   <-- [200] POST http://localhost:8000/payment/webhook
```

**NOT this:**

```
❌ Webhook signature verification failed
```

---

## 📞 Need Help?

Run the interactive helper:

```cmd
get_webhook_secret.bat
```

Or check the complete guide:

```cmd
notepad STRIPE_WEBHOOK_SETUP.md
```
