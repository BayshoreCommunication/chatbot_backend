# GitHub Secrets Setup for SMTP Email Functionality

## Issue

Subscription emails work locally but not on production because SMTP environment variables are missing from the GitHub Secrets.

## Root Cause

- ✅ Local `.env` file has SMTP configuration
- ✅ `docker-compose.yml` references SMTP variables
- ✅ `.github/workflows/deploy.yml` exports SMTP variables (lines 518-523)
- ❌ **GitHub Repository Secrets are MISSING the SMTP values**

## Solution: Add SMTP Secrets to GitHub Repository

### Step 1: Navigate to Repository Settings

1. Go to your GitHub repository
2. Click **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**

### Step 2: Add the Following Secrets

Click **New repository secret** for each of these:

| Secret Name     | Value                                       |
| --------------- | ------------------------------------------- |
| `SMPT_SERVICE`  | `gmail`                                     |
| `SMPT_HOST`     | `smtp.gmail.com`                            |
| `SMPT_PORT`     | `465`                                       |
| `SMPT_MAIL`     | `bayshoreai@gmail.com`                      |
| `SMPT_PASSWORD` | `rcwasfkrlkvshxbd`                          |
| `FRONTEND_URL`  | `https://chatbot-user-dashboard.vercel.app` |

### Step 3: Verify Existing Secrets

Make sure these secrets already exist (they should be present):

- ✅ MONGO_URI
- ✅ OPENAI_API_KEY
- ✅ STRIPE_SECRET_KEY
- ✅ STRIPE_WEBHOOK_SECRET
- ✅ JWT_SECRET_KEY
- ✅ REDIS_PASSWORD
- (and all others listed in deploy.yml lines 495-517)

### Step 4: Trigger Deployment

After adding the secrets, deploy by either:

- **Option A**: Push any commit to the `main` branch
- **Option B**: Go to **Actions** tab → **Deploy Backend** → **Run workflow**

### Step 5: Verify After Deployment

SSH into the server and check if SMTP variables are now present:

```bash
ssh root@bayshoreVM
docker exec chatbot-backend env | grep SMPT_
```

Expected output:

```
SMPT_SERVICE=gmail
SMPT_HOST=smtp.gmail.com
SMPT_PORT=465
SMPT_MAIL=bayshoreai@gmail.com
SMPT_PASSWORD=rcwasfkrlkvshxbd
```

### Step 6: Test Email Functionality

1. Create a new test subscription in Stripe Dashboard
2. Check server logs for email sending confirmation:
   ```bash
   docker logs chatbot-backend --tail 100 | grep -i "email\|smtp"
   ```
3. Cancel the test subscription
4. Check if cancellation email was sent

## Additional Issue: Webhook 404 Errors

The logs show webhook 404 errors because Stripe is sending to `/webhook` but the endpoint is `/payment/webhook`.

### Fix Webhook URL in Stripe Dashboard:

1. Go to Stripe Dashboard → **Developers** → **Webhooks**
2. Find your production webhook endpoint
3. Update the URL from:
   - ❌ `https://your-domain.com/webhook`
   - ✅ `https://your-domain.com/payment/webhook`
4. Events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

## Summary

1. ✅ Code is correct (docker-compose.yml has SMTP vars)
2. ✅ Workflow is correct (deploy.yml exports SMTP vars)
3. ❌ **GitHub Secrets need to be added** (missing SMTP values)
4. After adding secrets, redeploy to fix email functionality

## Timeline

- **Before**: Emails work locally (reading from `.env`) but not on production
- **After**: Emails will work on production (reading from GitHub Secrets → Docker environment)
