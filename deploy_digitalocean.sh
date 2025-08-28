#!/bin/bash

# DigitalOcean Deployment Script for Chatbot Backend
# This script sets up the complete environment for WebSocket-enabled chatbot backend

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN_NAME=""
SERVER_IP=""
PROJECT_DIR="/var/www/chatbot_backend"
SERVICE_NAME="chatbot-backend"

echo -e "${BLUE}🚀 DigitalOcean Chatbot Backend Deployment Script${NC}"
echo "=================================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   exit 1
fi

# Get domain name
read -p "Enter your domain name (e.g., api.yourdomain.com): " DOMAIN_NAME
if [[ -z "$DOMAIN_NAME" ]]; then
    echo -e "${RED}❌ Domain name is required${NC}"
    exit 1
fi

# Get server IP
read -p "Enter your server IP address: " SERVER_IP
if [[ -z "$SERVER_IP" ]]; then
    echo -e "${RED}❌ Server IP is required${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration:${NC}"
echo "   Domain: $DOMAIN_NAME"
echo "   Server IP: $SERVER_IP"
echo "   Project Directory: $PROJECT_DIR"
echo ""

# Update system
echo -e "${YELLOW}📦 Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# Install required packages
echo -e "${YELLOW}📦 Installing required packages...${NC}"
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl wget htop ufw

# Install Node.js (for Socket.IO client testing)
echo -e "${YELLOW}📦 Installing Node.js...${NC}"
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Configure firewall
echo -e "${YELLOW}🔥 Configuring firewall...${NC}"
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Create project directory
echo -e "${YELLOW}📁 Creating project directory...${NC}"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR

# Clone or copy project files
if [[ -d ".git" ]]; then
    echo -e "${YELLOW}📁 Copying current project to server...${NC}"
    sudo cp -r . $PROJECT_DIR/
else
    echo -e "${YELLOW}📁 Please copy your project files to $PROJECT_DIR${NC}"
    echo "   You can use scp, rsync, or git clone"
    read -p "Press Enter when files are copied..."
fi

# Set up Python virtual environment
echo -e "${YELLOW}🐍 Setting up Python virtual environment...${NC}"
cd $PROJECT_DIR
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Install additional WebSocket testing dependencies
pip install websockets python-socketio[client] requests

# Create environment file
echo -e "${YELLOW}⚙️ Creating environment configuration...${NC}"
cat > .env << EOF
# Database Configuration
MONGO_URI=your-mongodb-connection-string

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENV=your-pinecone-environment
PINECONE_INDEX=your-pinecone-index

# Optional: Stripe Configuration
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret

# Optional: Calendly Configuration
CALENDLY_API_KEY=your-calendly-api-key

# Optional: DigitalOcean Spaces
DO_SPACES_KEY=your-do-spaces-key
DO_SPACES_SECRET=your-do-spaces-secret
DO_SPACES_BUCKET=your-bucket-name
DO_SPACES_REGION=nyc3
DO_FOLDER_NAME=ai_bot

# Logging
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
EOF

echo -e "${GREEN}✅ Environment file created. Please edit $PROJECT_DIR/.env with your actual values${NC}"

# Create systemd service
echo -e "${YELLOW}🔧 Creating systemd service...${NC}"
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Chatbot Backend FastAPI Application
After=network.target

[Service]
Type=exec
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5

# Environment variables
Environment=PYTHONUNBUFFERED=1
Environment=UVICORN_ACCESS_LOG=1

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
echo -e "${YELLOW}🌐 Creating nginx configuration...${NC}"
sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;
    
    # Redirect HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN_NAME;
    
    # SSL Configuration (will be updated by certbot)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    
    # SSL Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # WebSocket Support for Socket.IO
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # WebSocket specific settings
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 86400;
    }
    
    # Native WebSocket Support
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # WebSocket specific settings
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 86400;
    }
    
    # Regular API endpoints
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # CORS headers
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization,X-API-Key" always;
        add_header Access-Control-Expose-Headers "Content-Length,Content-Range" always;
        
        # Handle preflight requests
        if (\$request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin * always;
            add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
            add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization,X-API-Key" always;
            add_header Access-Control-Max-Age 1728000 always;
            add_header Content-Type 'text/plain; charset=utf-8' always;
            add_header Content-Length 0 always;
            return 204;
        }
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo -e "${YELLOW}🔍 Testing nginx configuration...${NC}"
sudo nginx -t

# Get SSL certificate
echo -e "${YELLOW}🔒 Getting SSL certificate...${NC}"
sudo certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos --email admin@$DOMAIN_NAME

# Set up SSL auto-renewal
echo -e "${YELLOW}🔄 Setting up SSL auto-renewal...${NC}"
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

# Set proper permissions
echo -e "${YELLOW}🔐 Setting proper permissions...${NC}"
sudo chown -R $USER:$USER $PROJECT_DIR
sudo chmod -R 755 $PROJECT_DIR

# Enable and start services
echo -e "${YELLOW}🚀 Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME
sudo systemctl restart nginx

# Wait for service to start
echo -e "${YELLOW}⏳ Waiting for service to start...${NC}"
sleep 5

# Check service status
echo -e "${YELLOW}🔍 Checking service status...${NC}"
sudo systemctl status $SERVICE_NAME --no-pager

# Test endpoints
echo -e "${YELLOW}🧪 Testing endpoints...${NC}"
echo "Testing health endpoint..."
curl -s https://$DOMAIN_NAME/healthz || echo "Health endpoint test failed"

echo "Testing main endpoint..."
curl -s https://$DOMAIN_NAME/health || echo "Main endpoint test failed"

# Create deployment script
echo -e "${YELLOW}📝 Creating deployment script...${NC}"
cat > $PROJECT_DIR/deploy.sh << 'EOF'
#!/bin/bash

# Stop the service
sudo systemctl stop chatbot-backend

# Pull latest changes (if using git)
# git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Set proper permissions
sudo chown -R $USER:$USER /var/www/chatbot_backend
sudo chmod -R 755 /var/www/chatbot_backend

# Restart the service
sudo systemctl start chatbot-backend

# Check status
sudo systemctl status chatbot-backend

# Test WebSocket endpoints
echo "Testing WebSocket endpoints..."
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/health

echo "Deployment completed!"
EOF

chmod +x $PROJECT_DIR/deploy.sh

# Create WebSocket test script
echo -e "${YELLOW}📝 Creating WebSocket test script...${NC}"
cat > $PROJECT_DIR/test_websocket.sh << 'EOF'
#!/bin/bash

echo "🧪 Testing WebSocket functionality..."

# Test health endpoints
echo "Testing health endpoints..."
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/health

# Test WebSocket with wscat (if installed)
if command -v wscat &> /dev/null; then
    echo "Testing native WebSocket..."
    echo "Hello WebSocket!" | wscat -c ws://localhost:8000/ws
fi

echo "WebSocket tests completed!"
EOF

chmod +x $PROJECT_DIR/test_websocket.sh

# Install wscat for WebSocket testing
echo -e "${YELLOW}📦 Installing WebSocket testing tools...${NC}"
npm install -g wscat

# Final instructions
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo "1. Edit $PROJECT_DIR/.env with your actual API keys and configuration"
echo "2. Restart the service: sudo systemctl restart $SERVICE_NAME"
echo "3. Test WebSocket functionality: $PROJECT_DIR/test_websocket.sh"
echo "4. Monitor logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo -e "${BLUE}🔗 Your endpoints:${NC}"
echo "   Main API: https://$DOMAIN_NAME"
echo "   Health Check: https://$DOMAIN_NAME/healthz"
echo "   WebSocket: wss://$DOMAIN_NAME/ws"
echo "   Socket.IO: https://$DOMAIN_NAME/socket.io/"
echo ""
echo -e "${BLUE}📚 Useful commands:${NC}"
echo "   View logs: sudo journalctl -u $SERVICE_NAME -f"
echo "   Restart service: sudo systemctl restart $SERVICE_NAME"
echo "   Check status: sudo systemctl status $SERVICE_NAME"
echo "   Test WebSocket: $PROJECT_DIR/test_websocket.sh"
echo "   Deploy updates: $PROJECT_DIR/deploy.sh"
echo ""
echo -e "${GREEN}✅ Your WebSocket-enabled chatbot backend is now running on DigitalOcean!${NC}"
