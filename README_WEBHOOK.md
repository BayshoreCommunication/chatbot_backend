# 🚀 Quick Start - Stripe Webhook Testing

## ⚡ Super Fast Start (3 Commands)

```cmd
# 1. Start backend
uvicorn main:app --reload --port 8000

# 2. Start Stripe listener (in new terminal)
stripe listen --forward-to http://localhost:8000/payment/webhook

# 3. Test it (in another terminal)
stripe trigger checkout.session.completed
```

---

## 🎯 Easier Way - Use the Helper Script

Just double-click: **`QUICK_START.bat`**

It will:

1. ✅ Start your backend automatically
2. ✅ Start Stripe webhook listener
3. ✅ Guide you through testing
4. ✅ Verify database updates

---

## 📋 Step by Step (Manual)

### Terminal 1: Backend Server

```cmd
cd d:\bayai-chatbot\chatbot_backend
python -m uvicorn main:app --reload --port 8000
```

**Keep running!** Wait for "Application startup complete"

### Terminal 2: Stripe Webhook Listener

```cmd
cd d:\bayai-chatbot\chatbot_backend
stripe listen --forward-to http://localhost:8000/payment/webhook
```

**⚠️ IMPORTANT:** Copy the webhook secret that appears:

```
Your webhook signing secret is whsec_xxxxxxxxxxxxx
```

Update your `.env` file:

```properties
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx  # ← Use YOUR new secret
```

**Then restart Terminal 1** (backend server)!

### Terminal 3: Test Commands

```cmd
cd d:\bayai-chatbot\chatbot_backend

# Trigger test events
stripe trigger checkout.session.completed

# Check database
python check_webhook_activity.py
```

---

## ✅ What Success Looks Like

### In Terminal 1 (Backend):

```
INFO: Received webhook event: checkout.session.completed
INFO: Processing checkout completion for session: cs_test_xxxxx
INFO: ✅ Confirmation email sent successfully to user@example.com
```

### In Terminal 2 (Stripe Listener):

```
2025-01-18 10:30:45   --> checkout.session.completed [evt_xxxxx]
2025-01-18 10:30:45   <-- [200] POST http://localhost:8000/payment/webhook
```

### In Terminal 3 (Database Check):

```python
User: test@example.com
  ✅ subscription_type: professional
  ✅ subscription_start_date: 2025-01-18 10:30:00
  ✅ subscription_end_date: 2025-02-18 10:30:00
  ✅ stripe_subscription_id: sub_xxxxx
  ✅ stripe_customer_id: cus_xxxxx
```

---

## 🐛 Quick Troubleshooting

| Problem                         | Solution                                                            |
| ------------------------------- | ------------------------------------------------------------------- |
| `stripe: command not found`     | Download from: https://github.com/stripe/stripe-cli/releases/latest |
| `Connection refused`            | Make sure backend is running on port 8000                           |
| `Signature verification failed` | Update STRIPE_WEBHOOK_SECRET in .env and restart backend            |
| No logs in backend              | Check Stripe listener shows [200] response                          |
| Fields not in database          | Run: `python add_subscription_fields.py` for existing users         |

---

## 📚 More Help

- **Complete guide**: Open `STRIPE_WEBHOOK_SETUP.md`
- **Interactive menu**: Run `webhook_helper.bat`
- **Pre-flight check**: Run `python preflight_check.py`
- **Verify setup**: Run `python test_webhook_setup.py`

---

## 🎯 Current Status

✅ Stripe CLI installed (version 1.23.10)
✅ Backend code ready
✅ Webhook endpoint configured
✅ MongoDB connected
✅ SMTP configured

**You're ready to test!** Just run the 3 commands at the top. 🚀
