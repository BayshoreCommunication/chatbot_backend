@echo off
echo.
echo ========================================
echo   DEPLOY FIX TO PRODUCTION SERVER
echo ========================================
echo.
echo This will:
echo 1. Commit changes to git
echo 2. Push to GitHub
echo.
echo After this, you need to SSH to your server and run:
echo   cd /root/chatbot_backend ^&^& git pull ^&^& docker-compose down ^&^& docker-compose up -d --build
echo.
pause

echo.
echo Step 1: Adding files to git...
git add docker-compose.yml fix_network.sh fix_network.bat diagnose_network.sh NETWORK_FIX.md EMAIL_FIX_SUMMARY.md DEPLOY_NOW.md

echo.
echo Step 2: Committing changes...
git commit -m "fix: add DNS and network config to resolve [Errno 101] Network unreachable for email sending"

echo.
echo Step 3: Pushing to GitHub...
git push origin main

echo.
echo ========================================
echo   LOCAL CHANGES PUSHED TO GITHUB
echo ========================================
echo.
echo NEXT: SSH to your production server and run these commands:
echo.
echo ssh root@68.183.227.9
echo.
echo Then copy and paste this command:
echo.
echo cd /root/chatbot_backend ^&^& git pull origin main ^&^& docker-compose down ^&^& docker network prune -f ^&^& docker-compose up -d --build
echo.
echo ========================================
echo.
pause
