# DigitalOcean Deployment Guide

## Common Issues and Solutions

### 1. Environment Variables

Make sure all required environment variables are set in your DigitalOcean droplet:

```bash
# Required for core functionality
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
OPENAI_API_KEY=sk-your-openai-key
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENV=your-pinecone-environment
PINECONE_INDEX=your-pinecone-index

# Optional for enhanced features
CALENDLY_API_KEY=your-calendly-key
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
```

### 2. Feature Availability Issues

The following features should work even without all API keys:

- **FAQ Management System**: Works with basic functionality even without Pinecone
- **Appointment & Booking Integration**: Works with basic functionality even without Calendly
- **Appointment Availability Configuration**: Always available

### 3. Database Connection Issues

If you're experiencing database connection issues:

1. Check if MongoDB Atlas IP whitelist includes your DigitalOcean droplet IP
2. Verify the MONGO_URI is correct
3. Ensure the database user has proper permissions

### 4. Service Startup Issues

If services fail to start:

1. Check the logs: `journalctl -u your-service-name -f`
2. Verify all dependencies are installed: `pip install -r requirements.txt`
3. Ensure Python version compatibility

### 5. CORS Issues

If you're experiencing CORS issues in production:

1. Update the origins list in `main.py` to include your production domain
2. Ensure the frontend is making requests to the correct API URL

### 6. File Permissions

Ensure proper file permissions:

```bash
sudo chown -R www-data:www-data /var/www/chatbot_backend
sudo chmod -R 755 /var/www/chatbot_backend
```

### 7. Health Check Endpoint

Use the health check endpoint to verify all services are working:

```bash
curl https://your-domain.com/health
```

This will show the status of all services and help identify which ones are failing.

### 8. Debug Mode

For debugging, you can temporarily enable more verbose logging by setting:

```bash
export LOG_LEVEL=DEBUG
```

### 9. Restart Services

After making changes:

```bash
sudo systemctl restart your-chatbot-service
sudo systemctl status your-chatbot-service
```

### 10. Common Error Messages

- **"MongoDB connection failed"**: Check MONGO_URI and network connectivity
- **"OpenAI API key not found"**: Verify OPENAI_API_KEY is set
- **"Pinecone index not found"**: Check PINECONE_API_KEY and index name
- **"Service unavailable"**: Check if the service is running and accessible

## Quick Fix Commands

```bash
# Check environment variables
env | grep -E "(MONGO|OPENAI|PINECONE|CALENDLY)"

# Check service status
sudo systemctl status your-service-name

# View logs
sudo journalctl -u your-service-name -f

# Restart service
sudo systemctl restart your-service-name

# Test API endpoints
curl -H "X-API-Key: your-api-key" https://your-domain.com/api/conversations
```
