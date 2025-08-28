# WebSocket Setup Guide for Chatbot Backend

## Current WebSocket Implementation Review

### ✅ What's Working Well

1. **Dual WebSocket Support**: Your implementation supports both:

   - **Socket.IO** (for real-time chat functionality)
   - **Native FastAPI WebSocket** (for testing and simple connections)

2. **Proper App Configuration**: The app correctly switches between Socket.IO wrapped app and regular FastAPI app based on availability.

3. **CORS Configuration**: WebSocket headers are properly configured in CORS middleware.

4. **Error Handling**: Good error handling and fallback mechanisms.

### 🔧 Current Implementation Analysis

```python
# Socket.IO Configuration (in routes/chatbot.py)
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode='asgi',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8,
    allow_upgrades=True,
    transports=['websocket', 'polling'],
    cors_credentials=True,
    always_connect=True
)
```

**✅ Good Settings:**

- `cors_allowed_origins="*"` - Allows all origins
- `transports=['websocket', 'polling']` - Fallback support
- `ping_timeout=60, ping_interval=25` - Good for production
- `logger=True, engineio_logger=True` - Good for debugging

## Local Development Testing

### 1. Test Socket.IO Connection

```javascript
// Browser console or Node.js
const io = require("socket.io-client");

const socket = io("http://localhost:8000", {
  transports: ["websocket", "polling"],
  query: {
    apiKey: "your-api-key",
  },
});

socket.on("connect", () => {
  console.log("Connected to Socket.IO");
});

socket.on("connection_confirmed", (data) => {
  console.log("Connection confirmed:", data);
});

socket.on("new_message", (data) => {
  console.log("New message:", data);
});
```

### 2. Test Native WebSocket

```javascript
// Browser console
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
  console.log("Connected to WebSocket");
  ws.send("Hello WebSocket!");
};

ws.onmessage = (event) => {
  console.log("Received:", event.data);
};

ws.onclose = () => {
  console.log("WebSocket closed");
};
```

### 3. Test Health Endpoints

```bash
# Test health check
curl http://localhost:8000/healthz

# Test main health
curl http://localhost:8000/health
```

## DigitalOcean Server Setup

### 1. Nginx Configuration for WebSocket Support

Create `/etc/nginx/sites-available/chatbot-backend`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # WebSocket Support
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # WebSocket specific settings
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 86400;
    }

    # Native WebSocket Support
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # WebSocket specific settings
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 86400;
    }

    # Regular API endpoints
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # CORS headers
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization,X-API-Key" always;
        add_header Access-Control-Expose-Headers "Content-Length,Content-Range" always;

        # Handle preflight requests
        if ($request_method = 'OPTIONS') {
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
```

### 2. Systemd Service Configuration

Create `/etc/systemd/system/chatbot-backend.service`:

```ini
[Unit]
Description=Chatbot Backend FastAPI Application
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/chatbot_backend
Environment=PATH=/var/www/chatbot_backend/venv/bin
ExecStart=/var/www/chatbot_backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5

# Environment variables
Environment=MONGO_URI=your-mongo-uri
Environment=OPENAI_API_KEY=your-openai-key
Environment=PINECONE_API_KEY=your-pinecone-key
Environment=PINECONE_ENV=your-pinecone-env
Environment=PINECONE_INDEX=your-pinecone-index

# WebSocket specific settings
Environment=PYTHONUNBUFFERED=1
Environment=UVICORN_ACCESS_LOG=1

[Install]
WantedBy=multi-user.target
```

### 3. Deployment Script

Create `/var/www/chatbot_backend/deploy.sh`:

```bash
#!/bin/bash

# Stop the service
sudo systemctl stop chatbot-backend

# Pull latest changes
cd /var/www/chatbot_backend
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Set proper permissions
sudo chown -R www-data:www-data /var/www/chatbot_backend
sudo chmod -R 755 /var/www/chatbot_backend

# Restart the service
sudo systemctl start chatbot-backend
sudo systemctl enable chatbot-backend

# Check status
sudo systemctl status chatbot-backend

# Test WebSocket endpoints
echo "Testing WebSocket endpoints..."
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/health

echo "Deployment completed!"
```

### 4. SSL Certificate Setup

```bash
# Install Certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add this line:
0 12 * * * /usr/bin/certbot renew --quiet
```

### 5. Firewall Configuration

```bash
# Allow HTTP, HTTPS, and SSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 22
sudo ufw enable
```

## Testing WebSocket on DigitalOcean

### 1. Test Socket.IO Connection

```javascript
// Replace with your domain
const socket = io("https://your-domain.com", {
  transports: ["websocket", "polling"],
  query: {
    apiKey: "your-api-key",
  },
  secure: true,
});

socket.on("connect", () => {
  console.log("Connected to Socket.IO on DigitalOcean");
});

socket.on("connection_confirmed", (data) => {
  console.log("Connection confirmed:", data);
});
```

### 2. Test Native WebSocket

```javascript
// Replace with your domain
const ws = new WebSocket("wss://your-domain.com/ws");

ws.onopen = () => {
  console.log("Connected to WebSocket on DigitalOcean");
  ws.send("Hello from DigitalOcean!");
};

ws.onmessage = (event) => {
  console.log("Received:", event.data);
};
```

### 3. Monitor WebSocket Connections

```bash
# Check service logs
sudo journalctl -u chatbot-backend -f

# Check nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Monitor WebSocket connections
sudo netstat -tulpn | grep :8000
```

## Troubleshooting

### Common Issues and Solutions

1. **WebSocket Connection Fails**

   ```bash
   # Check if service is running
   sudo systemctl status chatbot-backend

   # Check nginx configuration
   sudo nginx -t
   sudo systemctl restart nginx
   ```

2. **CORS Issues**

   - Verify nginx CORS headers
   - Check browser console for CORS errors
   - Ensure frontend is using correct protocol (http/https)

3. **SSL/HTTPS Issues**

   ```bash
   # Check SSL certificate
   sudo certbot certificates

   # Renew if needed
   sudo certbot renew
   ```

4. **Performance Issues**

   ```bash
   # Monitor system resources
   htop

   # Check WebSocket connections
   ss -tulpn | grep :8000
   ```

## Production Optimization

### 1. Redis for Socket.IO (Optional)

For better scalability, add Redis adapter:

```python
# In routes/chatbot.py
import socketio
from socketio import AsyncRedisManager

# Initialize Redis manager
redis_manager = AsyncRedisManager('redis://localhost:6379/0')

sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode='asgi',
    client_manager=redis_manager,
    # ... other settings
)
```

### 2. Load Balancing

For multiple instances, use Redis adapter and load balancer:

```nginx
upstream chatbot_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

location /socket.io/ {
    proxy_pass http://chatbot_backend;
    # ... other settings
}
```

### 3. Monitoring

Add monitoring endpoints:

```python
@app.get("/websocket-status")
async def websocket_status():
    if sio:
        return {
            "status": "active",
            "connections": len(sio.manager.rooms),
            "socket_io": "available"
        }
    return {"status": "inactive", "socket_io": "unavailable"}
```

## Summary

Your WebSocket implementation is **solid and production-ready**. The dual approach (Socket.IO + native WebSocket) provides excellent flexibility. The main areas for DigitalOcean deployment are:

1. ✅ **Nginx configuration** for WebSocket proxy
2. ✅ **SSL certificate** setup
3. ✅ **Systemd service** configuration
4. ✅ **Proper firewall** settings
5. ✅ **Monitoring and logging**

The implementation should work perfectly on both local and DigitalOcean environments with the provided configuration.
