#!/bin/bash

# Server Log Checker Script
# Usage: ./check_server_logs.sh [option]
# Options: email, subscription, error, all

echo "🔍 Checking Server Logs..."
echo "================================"

OPTION=${1:-all}

case $OPTION in
  email)
    echo "📧 Checking email-related logs..."
    sudo docker logs chatbot-backend 2>&1 | grep -i "email" | tail -50
    sudo docker logs chatbot-backend 2>&1 | grep -i "smtp" | tail -50
    ;;
  
  subscription)
    echo "💳 Checking subscription-related logs..."
    sudo docker logs chatbot-backend 2>&1 | grep -i "subscription" | tail -50
    sudo docker logs chatbot-backend 2>&1 | grep -i "cancelled" | tail -50
    sudo docker logs chatbot-backend 2>&1 | grep -i "customer.subscription" | tail -50
    ;;
  
  error)
    echo "❌ Checking error logs..."
    sudo docker logs chatbot-backend 2>&1 | grep -i "error" | tail -50
    sudo docker logs chatbot-backend 2>&1 | grep -i "failed" | tail -50
    ;;
  
  webhook)
    echo "🔗 Checking webhook logs..."
    sudo docker logs chatbot-backend 2>&1 | grep -i "webhook" | tail -100
    sudo docker logs chatbot-backend 2>&1 | grep -i "stripe" | tail -100
    ;;
  
  smtp)
    echo "📤 Checking SMTP logs..."
    sudo docker logs chatbot-backend 2>&1 | grep -i "smtp" | tail -50
    sudo docker logs chatbot-backend 2>&1 | grep -i "bayshoreai@gmail.com" | tail -50
    ;;
  
  recent)
    echo "⏱️ Last 100 log entries..."
    sudo docker logs chatbot-backend --tail 100
    ;;
  
  all)
    echo "📋 All recent logs (last 200 lines)..."
    sudo docker logs chatbot-backend --tail 200
    ;;
  
  *)
    echo "❓ Unknown option: $OPTION"
    echo "Available options: email, subscription, error, webhook, smtp, recent, all"
    exit 1
    ;;
esac

echo ""
echo "================================"
echo "✅ Log check complete!"
echo ""
echo "💡 Usage examples:"
echo "  ./check_server_logs.sh email         # Email logs only"
echo "  ./check_server_logs.sh subscription  # Subscription logs"
echo "  ./check_server_logs.sh webhook       # Webhook logs"
echo "  ./check_server_logs.sh error         # Error logs"
echo "  ./check_server_logs.sh smtp          # SMTP logs"
echo "  ./check_server_logs.sh recent        # Last 100 lines"
echo "  ./check_server_logs.sh all           # Last 200 lines"
