@echo off
echo ============================================================
echo  PORT 80 CONFLICT FIX - Docker Compose Error
echo ============================================================
echo.
echo This error means another program is using port 80.
echo Let's find and fix it!
echo.
pause

:check_port
cls
echo ============================================================
echo  STEP 1: Check What's Using Port 80
echo ============================================================
echo.
echo Checking port 80...
echo.
netstat -ano | findstr :80
echo.
echo Looking for LISTENING on port 80...
echo.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :80 ^| findstr LISTENING') do (
    echo Process ID using port 80: %%a
    echo.
    echo Process details:
    tasklist /FI "PID eq %%a"
)
echo.
pause

:menu
cls
echo ============================================================
echo  CHOOSE A SOLUTION
echo ============================================================
echo.
echo 1. Stop IIS (Internet Information Services)
echo 2. Stop Docker containers on port 80
echo 3. Change Docker Compose to use different port
echo 4. Check again
echo 5. Exit
echo.
choice /c 12345 /m "Select option"

if errorlevel 5 goto end
if errorlevel 4 goto check_port
if errorlevel 3 goto change_port
if errorlevel 2 goto stop_docker
if errorlevel 1 goto stop_iis

:stop_iis
cls
echo ============================================================
echo  STOPPING IIS (Internet Information Services)
echo ============================================================
echo.
echo This will stop Windows IIS web server...
echo.
net stop w3svc
if errorlevel 1 (
    echo.
    echo IIS not found or already stopped.
) else (
    echo.
    echo ✅ IIS stopped successfully!
)
echo.
echo To permanently disable IIS:
echo 1. Open Services (services.msc)
echo 2. Find "World Wide Web Publishing Service"
echo 3. Right-click → Properties → Startup type: Disabled
echo.
pause
goto check_port

:stop_docker
cls
echo ============================================================
echo  STOPPING DOCKER CONTAINERS
echo ============================================================
echo.
echo Stopping all Docker containers...
echo.
docker stop $(docker ps -q)
echo.
echo ✅ All containers stopped!
echo.
pause
goto check_port

:change_port
cls
echo ============================================================
echo  CHANGE DOCKER COMPOSE PORT
echo ============================================================
echo.
echo Instead of using port 80, we can use a different port.
echo Common alternatives: 8080, 8888, 3000
echo.
set /p newport="Enter new port number (e.g., 8080): "
echo.
echo Updating docker-compose.yml...
echo.

REM Backup original file
copy d:\bayai-chatbot\chatbot_backend\docker-compose.yml d:\bayai-chatbot\chatbot_backend\docker-compose.yml.backup

REM This is simplified - you'll need to manually edit or use PowerShell
echo ⚠️  Manual step required:
echo.
echo Open: d:\bayai-chatbot\chatbot_backend\docker-compose.yml
echo.
echo Find this line:
echo   - "80:80"
echo.
echo Change to:
echo   - "%newport%:80"
echo.
echo Then save and try: docker-compose up -d
echo.
notepad d:\bayai-chatbot\chatbot_backend\docker-compose.yml
pause
goto menu

:end
echo.
echo Goodbye!
exit
