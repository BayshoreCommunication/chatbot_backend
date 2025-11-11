# Fix Docker Compose Port 80 Conflict

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Docker Port 80 Conflict - Automatic Fix" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check what's using port 80
Write-Host "Checking port 80..." -ForegroundColor Yellow
$port80 = Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue

if ($port80) {
    Write-Host "❌ Port 80 is in use!" -ForegroundColor Red
    Write-Host ""
    
    foreach ($conn in $port80) {
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Process using port 80:" -ForegroundColor Yellow
            Write-Host "  Name: $($process.ProcessName)" -ForegroundColor White
            Write-Host "  PID: $($process.Id)" -ForegroundColor White
            Write-Host "  Path: $($process.Path)" -ForegroundColor White
            Write-Host ""
        }
    }
    
    Write-Host "Common solutions:" -ForegroundColor Cyan
    Write-Host "1. Stop IIS: net stop w3svc" -ForegroundColor White
    Write-Host "2. Stop other Docker containers: docker stop `$(docker ps -q)" -ForegroundColor White
    Write-Host "3. Change port in docker-compose.yml" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Would you like to stop IIS? (Y/N)"
    
    if ($choice -eq "Y" -or $choice -eq "y") {
        Write-Host ""
        Write-Host "Stopping IIS..." -ForegroundColor Yellow
        Stop-Service W3SVC -ErrorAction SilentlyContinue
        
        if ($?) {
            Write-Host "✅ IIS stopped successfully!" -ForegroundColor Green
        } else {
            Write-Host "❌ Could not stop IIS. It may not be running." -ForegroundColor Red
        }
    }
    
} else {
    Write-Host "✅ Port 80 is available!" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Alternative: Change Docker Compose Port" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you want to use a different port (e.g., 8080):" -ForegroundColor Yellow
Write-Host ""

$changPort = Read-Host "Change Docker Compose to use port 8080 instead? (Y/N)"

if ($changePort -eq "Y" -or $changePort -eq "y") {
    $dockerComposePath = "d:\bayai-chatbot\chatbot_backend\docker-compose.yml"
    
    # Backup original
    Copy-Item $dockerComposePath "$dockerComposePath.backup" -Force
    Write-Host "✅ Backup created: docker-compose.yml.backup" -ForegroundColor Green
    
    # Read content
    $content = Get-Content $dockerComposePath -Raw
    
    # Replace port 80 with 8080
    $newContent = $content -replace '- "80:80"', '- "8080:80"'
    
    # Save
    Set-Content $dockerComposePath $newContent -NoNewline
    
    Write-Host "✅ Updated docker-compose.yml to use port 8080" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now you can access your app at: http://localhost:8080" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To start Docker Compose:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d" -ForegroundColor White
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
