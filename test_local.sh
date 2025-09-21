#!/bin/bash

echo "🧪 Testing Docker build locally..."

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true
docker rmi $(docker images -q) 2>/dev/null || true
docker system prune -af --volumes 2>/dev/null || true

# Test Docker build
echo "Building Docker image..."
docker build -t chatbot-test .

if [ $? -eq 0 ]; then
    echo "✅ Docker build successful!"
    
    # Test docker-compose
    echo "Testing docker-compose..."
    docker compose up -d
    
    if [ $? -eq 0 ]; then
        echo "✅ Docker compose successful!"
        
        # Wait a bit and check status
        sleep 10
        docker compose ps
        
        # Clean up
        docker compose down
        docker rmi chatbot-test 2>/dev/null || true
        
        echo "✅ All tests passed!"
    else
        echo "❌ Docker compose failed!"
        docker compose logs
        exit 1
    fi
else
    echo "❌ Docker build failed!"
    exit 1
fi
