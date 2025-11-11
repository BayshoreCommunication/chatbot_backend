@echo off
cls
echo ============================================================
echo  STRIPE WEBHOOK QUICK START
echo ============================================================
echo.
echo This script will help you set up and test Stripe webhooks
echo.
echo You have 3 terminals to manage:
echo   Terminal 1: Backend Server (FastAPI)
echo   Terminal 2: Stripe Webhook Listener  
echo   Terminal 3: Test Commands
echo.
echo ============================================================
pause

:step1
cls
echo ============================================================
echo  STEP 1: Start Backend Server
echo ============================================================
echo.
echo Opening Backend Server in a new window...
echo Keep this window running!
echo.
start "Backend Server" cmd /k "cd /d d:\bayai-chatbot\chatbot_backend && echo Starting FastAPI Backend... && uvicorn main:app --reload --port 8000"
echo.
echo Waiting 5 seconds for backend to start...
timeout /t 5 >nul
echo.
echo ✅ Backend should be running at http://localhost:8000
echo.
echo Press any key when you see "Application startup complete"
pause >nul

:step2
cls
echo ============================================================
echo  STEP 2: Check Stripe Login
echo ============================================================
echo.
echo Checking if you're logged into Stripe CLI...
echo.
stripe config --list >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Not logged in. Logging in now...
    echo A browser window will open. Click "Allow access"
    echo.
    pause
    stripe login
    echo.
) else (
    echo ✅ Already logged in to Stripe
)
echo.
pause

:step3
cls
echo ============================================================
echo  STEP 3: Start Webhook Listener
echo ============================================================
echo.
echo Opening Stripe Webhook Listener in a new window...
echo.
echo ⚠️  VERY IMPORTANT:
echo    1. Look for the webhook signing secret (starts with whsec_)
echo    2. COPY IT!
echo    3. Update it in your .env file:
echo       STRIPE_WEBHOOK_SECRET=whsec_xxxxx
echo.
pause
start "Stripe Webhook Listener" cmd /k "cd /d d:\bayai-chatbot\chatbot_backend && echo Starting Stripe Webhook Listener... && echo. && echo ⚠️  COPY THE WEBHOOK SECRET (whsec_xxxxx) AND UPDATE YOUR .env FILE! && echo. && stripe listen --forward-to http://localhost:8000/payment/webhook"
echo.
echo ✅ Webhook listener starting in new window...
echo.
echo Did you copy the webhook secret (whsec_xxxxx)?
choice /c YN /m "Have you updated .env with the new webhook secret"
if errorlevel 2 goto step3_reminder
if errorlevel 1 goto step4

:step3_reminder
cls
echo ============================================================
echo  HOW TO UPDATE .env FILE
echo ============================================================
echo.
echo 1. Open: d:\bayai-chatbot\chatbot_backend\.env
echo 2. Find line: STRIPE_WEBHOOK_SECRET=whsec_VmLKNEW7wagzQLo5H8mQxCJMWAJQHUWq
echo 3. Replace with: STRIPE_WEBHOOK_SECRET=whsec_xxxxx (your new secret)
echo 4. Save the file
echo 5. Go back to Backend Server window and press Ctrl+C
echo 6. Restart with: uvicorn main:app --reload --port 8000
echo.
pause
goto step3

:step4
cls
echo ============================================================
echo  STEP 4: Test Webhook
echo ============================================================
echo.
echo Choose a test event to trigger:
echo.
echo 1. Checkout Completed (New Subscription) - RECOMMENDED
echo 2. Subscription Created
echo 3. Subscription Updated  
echo 4. Subscription Deleted
echo 5. Payment Succeeded
echo 6. Payment Failed
echo 7. Skip testing for now
echo.
choice /c 1234567 /m "Enter your choice"

if errorlevel 7 goto step5
if errorlevel 6 (
    echo.
    echo Triggering: invoice.payment_failed
    stripe trigger invoice.payment_failed
    goto step4_result
)
if errorlevel 5 (
    echo.
    echo Triggering: invoice.payment_succeeded
    stripe trigger invoice.payment_succeeded
    goto step4_result
)
if errorlevel 4 (
    echo.
    echo Triggering: customer.subscription.deleted
    stripe trigger customer.subscription.deleted
    goto step4_result
)
if errorlevel 3 (
    echo.
    echo Triggering: customer.subscription.updated
    stripe trigger customer.subscription.updated
    goto step4_result
)
if errorlevel 2 (
    echo.
    echo Triggering: customer.subscription.created
    stripe trigger customer.subscription.created
    goto step4_result
)
if errorlevel 1 (
    echo.
    echo Triggering: checkout.session.completed
    stripe trigger checkout.session.completed
    goto step4_result
)

:step4_result
echo.
echo ✅ Event triggered!
echo.
echo Check the following:
echo   1. Backend Server window - Look for "Received webhook event"
echo   2. Stripe Listener window - Look for [200] POST response
echo.
pause
goto step4

:step5
cls
echo ============================================================
echo  STEP 5: Verify Database
echo ============================================================
echo.
echo Checking if subscription fields were created in database...
echo.
python check_webhook_activity.py
echo.
pause

:menu
cls
echo ============================================================
echo  WEBHOOK TESTING MENU
echo ============================================================
echo.
echo 1. Trigger another test event
echo 2. Check database again
echo 3. View backend logs
echo 4. View complete setup guide
echo 5. Restart everything
echo 6. Exit
echo.
choice /c 123456 /m "Enter your choice"

if errorlevel 6 goto end
if errorlevel 5 goto step1
if errorlevel 4 (
    notepad STRIPE_WEBHOOK_SETUP.md
    goto menu
)
if errorlevel 3 (
    echo.
    echo Backend logs are in the "Backend Server" window
    pause
    goto menu
)
if errorlevel 2 goto step5
if errorlevel 1 goto step4

:end
cls
echo ============================================================
echo  Cleaning Up
echo ============================================================
echo.
echo To stop the servers:
echo   1. Go to Backend Server window - Press Ctrl+C
echo   2. Go to Stripe Listener window - Press Ctrl+C
echo.
echo Thank you for using Stripe Webhook Quick Start!
echo.
pause
exit
