#!/bin/bash

# SMTP Configuration Verification Script
# Run this on the production server after adding GitHub Secrets

echo "================================================"
echo "SMTP Configuration Verification"
echo "================================================"
echo ""

# Check if container is running
echo "1. Checking if chatbot-backend container is running..."
if docker ps | grep -q chatbot-backend; then
    echo "   ✅ Container is running"
else
    echo "   ❌ Container is NOT running"
    exit 1
fi

echo ""

# Check SMTP environment variables in container
echo "2. Checking SMTP environment variables in container..."
SMPT_VARS=$(docker exec chatbot-backend env | grep "SMPT_\|FRONTEND_URL")

if [ -z "$SMPT_VARS" ]; then
    echo "   ❌ NO SMTP variables found in container"
    echo ""
    echo "   This means GitHub Secrets are not configured."
    echo "   Please add the following secrets to GitHub:"
    echo "   - SMPT_SERVICE"
    echo "   - SMPT_HOST"
    echo "   - SMPT_PORT"
    echo "   - SMPT_MAIL"
    echo "   - SMPT_PASSWORD"
    echo "   - FRONTEND_URL"
    echo ""
    echo "   Then redeploy the application."
else
    echo "   ✅ SMTP variables found:"
    echo "$SMPT_VARS" | sed 's/^/      /'
fi

echo ""

# Check recent logs for email activity
echo "3. Checking recent logs for email/SMTP activity..."
EMAIL_LOGS=$(docker logs chatbot-backend --tail 100 2>&1 | grep -i "email\|smtp" | tail -5)

if [ -z "$EMAIL_LOGS" ]; then
    echo "   ⚠️  No email-related logs found (this is expected if SMTP vars are missing)"
else
    echo "   Found email-related logs:"
    echo "$EMAIL_LOGS" | sed 's/^/      /'
fi

echo ""

# Check for webhook errors
echo "4. Checking for webhook 404 errors..."
WEBHOOK_ERRORS=$(docker logs chatbot-backend --tail 100 2>&1 | grep "404" | grep "webhook" | wc -l)

if [ "$WEBHOOK_ERRORS" -gt 0 ]; then
    echo "   ⚠️  Found $WEBHOOK_ERRORS webhook 404 errors"
    echo "   Update Stripe webhook URL to: /payment/webhook"
else
    echo "   ✅ No webhook 404 errors found"
fi

echo ""

# Check all environment variables (count)
echo "5. Checking total environment variables in container..."
ENV_COUNT=$(docker exec chatbot-backend env | wc -l)
echo "   Total environment variables: $ENV_COUNT"

# Expected minimum with SMTP
if [ "$ENV_COUNT" -ge 43 ]; then
    echo "   ✅ Environment variable count looks good"
else
    echo "   ⚠️  Expected at least 43 variables (including SMTP)"
fi

echo ""
echo "================================================"
echo "Summary"
echo "================================================"

if [ -z "$SMPT_VARS" ]; then
    echo "❌ SMTP NOT CONFIGURED - Add GitHub Secrets and redeploy"
    echo ""
    echo "Next steps:"
    echo "1. Go to GitHub repo → Settings → Secrets and variables → Actions"
    echo "2. Add SMTP secrets (SMPT_SERVICE, SMPT_HOST, SMPT_PORT, SMPT_MAIL, SMPT_PASSWORD, FRONTEND_URL)"
    echo "3. Push a commit or manually trigger deployment workflow"
    echo "4. Run this script again to verify"
else
    echo "✅ SMTP CONFIGURED - Email functionality should work"
    echo ""
    echo "Test by:"
    echo "1. Creating a test subscription"
    echo "2. Checking logs: docker logs chatbot-backend | grep -i email"
fi

echo ""
