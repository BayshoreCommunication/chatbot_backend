@echo off
cls
echo ============================================================
echo  STRIPE WEBHOOK SECRET COLLECTOR
echo ============================================================
echo.
echo This will help you get your Stripe webhook secret key.
echo.
echo Choose your setup:
echo   1. Local Testing (Stripe CLI)
echo   2. Production (Stripe Dashboard)
echo   3. Exit
echo.
choice /c 123 /m "Select option"

if errorlevel 3 goto end
if errorlevel 2 goto production
if errorlevel 1 goto local

:local
cls
echo ============================================================
echo  LOCAL TESTING - Stripe CLI Method
echo ============================================================
echo.
echo STEP 1: Make sure you're logged in to Stripe CLI
echo --------------------------------------------------------
echo.
stripe login
if errorlevel 1 (
    echo.
    echo ❌ Login failed. Please try again.
    pause
    goto local
)
echo.
echo ✅ Successfully logged in!
echo.
pause

echo.
echo STEP 2: Starting Stripe webhook listener...
echo --------------------------------------------------------
echo.
echo ⚠️  IMPORTANT: 
echo   - Look for "Your webhook signing secret is whsec_xxxxx"
echo   - COPY that entire secret (starts with whsec_)
echo   - Keep this window open
echo.
echo Press any key to start the listener...
pause >nul
echo.
echo Starting listener...
echo.
stripe listen --forward-to http://localhost:8000/payment/webhook
pause
goto menu

:production
cls
echo ============================================================
echo  PRODUCTION - Stripe Dashboard Method
echo ============================================================
echo.
echo Follow these steps:
echo.
echo 1. Open Stripe Dashboard in your browser:
echo    https://dashboard.stripe.com/test/webhooks
echo.
echo 2. Click "Add endpoint" button
echo.
echo 3. Enter your production URL:
echo    Example: https://your-backend.vercel.app/payment/webhook
echo.
echo 4. Select these events:
echo    - checkout.session.completed
echo    - customer.subscription.created
echo    - customer.subscription.updated
echo    - customer.subscription.deleted
echo    - invoice.payment_succeeded
echo    - invoice.payment_failed
echo.
echo 5. Click "Add endpoint"
echo.
echo 6. Click on the newly created endpoint
echo.
echo 7. Click "Reveal" under "Signing secret"
echo.
echo 8. COPY the secret (starts with whsec_)
echo.
echo.
choice /c YN /m "Open Stripe Dashboard in browser now"
if errorlevel 2 goto menu
if errorlevel 1 (
    start https://dashboard.stripe.com/test/webhooks
)

echo.
echo After copying the secret:
echo   1. Update your production environment variables
echo   2. Set: STRIPE_WEBHOOK_SECRET=whsec_xxxxx
echo   3. Restart your production server
echo.
pause
goto menu

:menu
cls
echo ============================================================
echo  NEXT STEPS
echo ============================================================
echo.
echo What would you like to do?
echo.
echo 1. Update .env file with new secret
echo 2. Test webhook with sample event
echo 3. View current .env configuration
echo 4. Start over
echo 5. Exit
echo.
choice /c 12345 /m "Select option"

if errorlevel 5 goto end
if errorlevel 4 goto local
if errorlevel 3 goto view_env
if errorlevel 2 goto test_webhook
if errorlevel 1 goto update_env

:update_env
cls
echo ============================================================
echo  UPDATE .env FILE
echo ============================================================
echo.
echo Current .env location: d:\bayai-chatbot\chatbot_backend\.env
echo.
echo Opening .env file in notepad...
echo.
echo Find this line:
echo   STRIPE_WEBHOOK_SECRET=whsec_VmLKNEW7wagzQLo5H8mQxCJMWAJQHUWq
echo.
echo Replace with your NEW secret:
echo   STRIPE_WEBHOOK_SECRET=whsec_xxxxx (paste your secret here)
echo.
pause
notepad d:\bayai-chatbot\chatbot_backend\.env
echo.
echo ✅ After saving, RESTART your backend server!
echo.
pause
goto menu

:test_webhook
cls
echo ============================================================
echo  TEST WEBHOOK
echo ============================================================
echo.
echo Make sure the following are running:
echo   1. Backend server (python -m uvicorn main:app --reload --port 8000)
echo   2. Stripe listener (stripe listen --forward-to ...)
echo.
choice /c YN /m "Are both running"
if errorlevel 2 (
    echo.
    echo Please start them first, then try again.
    pause
    goto menu
)

echo.
echo Triggering test event: checkout.session.completed
echo.
stripe trigger checkout.session.completed
echo.
echo ✅ Event triggered!
echo.
echo Check your backend logs for:
echo   - "Received webhook event: checkout.session.completed"
echo   - "✅ Confirmation email sent successfully"
echo.
pause

echo.
echo Checking database for updates...
echo.
python check_webhook_activity.py
echo.
pause
goto menu

:view_env
cls
echo ============================================================
echo  CURRENT .env CONFIGURATION
echo ============================================================
echo.
findstr "STRIPE_WEBHOOK_SECRET" d:\bayai-chatbot\chatbot_backend\.env
echo.
echo Full .env file:
echo.
type d:\bayai-chatbot\chatbot_backend\.env
echo.
pause
goto menu

:end
cls
echo ============================================================
echo  Summary
echo ============================================================
echo.
echo Remember:
echo   - LOCAL: Use secret from 'stripe listen' command
echo   - PRODUCTION: Use secret from Stripe Dashboard
echo   - Always restart backend after changing .env
echo.
echo Documentation:
echo   - Full guide: STRIPE_WEBHOOK_SETUP.md
echo   - Quick start: README_WEBHOOK.md
echo.
pause
exit
