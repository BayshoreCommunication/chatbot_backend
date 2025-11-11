@echo off
echo ======================================
echo Stripe Webhook Testing Helper
echo ======================================
echo.

:menu
echo Choose an option:
echo.
echo 1. Check if Stripe CLI is installed
echo 2. Login to Stripe
echo 3. Start Backend Server
echo 4. Start Stripe Webhook Listener
echo 5. Test Webhook (trigger event)
echo 6. Check Database for Subscription Fields
echo 7. View Complete Setup Guide
echo 8. Exit
echo.
set /p choice="Enter choice (1-8): "

if "%choice%"=="1" goto check_stripe
if "%choice%"=="2" goto login_stripe
if "%choice%"=="3" goto start_backend
if "%choice%"=="4" goto start_listener
if "%choice%"=="5" goto test_webhook
if "%choice%"=="6" goto check_db
if "%choice%"=="7" goto view_guide
if "%choice%"=="8" goto end

:check_stripe
echo.
echo Checking Stripe CLI installation...
echo.
stripe --version
if errorlevel 1 (
    echo.
    echo ❌ Stripe CLI is NOT installed!
    echo.
    echo Download from: https://github.com/stripe/stripe-cli/releases/latest
    echo Look for: stripe_X.X.X_windows_x86_64.zip
    echo.
    echo After downloading:
    echo 1. Extract stripe.exe
    echo 2. Move to C:\stripe\
    echo 3. Add C:\stripe to PATH environment variable
    echo 4. Restart this terminal
    echo.
) else (
    echo ✅ Stripe CLI is installed!
)
pause
goto menu

:login_stripe
echo.
echo Opening browser to login to Stripe...
echo.
stripe login
echo.
if errorlevel 1 (
    echo ❌ Login failed
) else (
    echo ✅ Login successful!
)
pause
goto menu

:start_backend
echo.
echo Starting FastAPI Backend...
echo This will open in a new window. Keep it running!
echo.
start cmd /k "cd /d d:\bayai-chatbot\chatbot_backend && uvicorn main:app --reload --port 8000"
echo.
echo ✅ Backend starting in new window...
echo Wait 5 seconds for it to start, then check http://localhost:8000/docs
timeout /t 5
pause
goto menu

:start_listener
echo.
echo Starting Stripe Webhook Listener...
echo.
echo ⚠️  IMPORTANT: Copy the webhook secret (whsec_xxxxx) that appears!
echo You'll need to add it to your .env file.
echo.
pause
echo.
stripe listen --forward-to http://localhost:8000/payment/webhook
pause
goto menu

:test_webhook
echo.
echo Testing Webhook...
echo.
echo Available test events:
echo 1. checkout.session.completed (New subscription)
echo 2. customer.subscription.created (Subscription created)
echo 3. customer.subscription.updated (Subscription updated)
echo 4. customer.subscription.deleted (Subscription cancelled)
echo 5. invoice.payment_succeeded (Payment successful)
echo 6. invoice.payment_failed (Payment failed)
echo.
set /p event="Enter choice (1-6): "

if "%event%"=="1" stripe trigger checkout.session.completed
if "%event%"=="2" stripe trigger customer.subscription.created
if "%event%"=="3" stripe trigger customer.subscription.updated
if "%event%"=="4" stripe trigger customer.subscription.deleted
if "%event%"=="5" stripe trigger invoice.payment_succeeded
if "%event%"=="6" stripe trigger invoice.payment_failed

echo.
echo ✅ Event triggered! Check your backend logs.
pause
goto menu

:check_db
echo.
echo Checking database for subscription fields...
echo.
python check_webhook_activity.py
pause
goto menu

:view_guide
echo.
echo Opening setup guide...
notepad STRIPE_WEBHOOK_SETUP.md
goto menu

:end
echo.
echo Goodbye!
exit /b
