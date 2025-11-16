@echo off
REM Fix Docker Network for Email Sending
REM This script recreates containers with proper network configuration

echo 🔧 Fixing Docker network configuration for email sending...
echo.

REM Stop and remove existing containers
echo 📦 Stopping existing containers...
docker-compose down

REM Remove any dangling networks
echo 🧹 Cleaning up old networks...
docker network prune -f

REM Rebuild and restart with new network configuration
echo 🚀 Rebuilding containers with proper network settings...
docker-compose up -d --build

REM Wait for containers to be ready
echo ⏳ Waiting for containers to be ready...
timeout /t 10 /nobreak >nul

REM Check container status
echo.
echo ✅ Container status:
docker-compose ps

echo.
echo ✅ Network configuration updated!
echo 📧 Email sending should now work. Test by creating a new subscription.
echo.
pause
