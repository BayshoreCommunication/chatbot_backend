#!/bin/bash

# Fix Docker Network for Email Sending
# This script recreates containers with proper network configuration

echo "🔧 Fixing Docker network configuration for email sending..."

# Stop and remove existing containers
echo "📦 Stopping existing containers..."
docker-compose down

# Remove any dangling networks
echo "🧹 Cleaning up old networks..."
docker network prune -f

# Rebuild and restart with new network configuration
echo "🚀 Rebuilding containers with proper network settings..."
docker-compose up -d --build

# Wait for containers to be healthy
echo "⏳ Waiting for containers to be ready..."
sleep 10

# Check container status
echo "✅ Container status:"
docker-compose ps

# Test network connectivity from backend container
echo ""
echo "🌐 Testing network connectivity to Gmail SMTP..."
docker exec chatbot-backend ping -c 3 smtp.gmail.com || echo "⚠️  Ping may be blocked (normal), but DNS should resolve"

# Check DNS resolution
echo ""
echo "🔍 Testing DNS resolution..."
docker exec chatbot-backend nslookup smtp.gmail.com || echo "⚠️  nslookup not available"

# Test SMTP connection (port 465)
echo ""
echo "📧 Testing SMTP port connectivity..."
docker exec chatbot-backend timeout 5 bash -c "cat < /dev/null > /dev/tcp/smtp.gmail.com/465" && echo "✅ SMTP port 465 reachable" || echo "❌ Cannot reach SMTP port 465"

echo ""
echo "✅ Network configuration updated!"
echo "📧 Email sending should now work. Test by creating a new subscription."
