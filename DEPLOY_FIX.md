# DEPLOY FIX TO PRODUCTION SERVER

## What Was Fixed

The code now has **BACKWARD COMPATIBILITY** - works with both:
- ✅ Old langchain (< 0.3.18) - uses `load_qa_chain`
- ✅ New langchain (>= 0.3.18) - uses `create_stuff_documents_chain`

**No core logic changed** - just added import fallbacks.

## Deploy to Production (Choose Your Method)

### Method 1: Git Deploy (RECOMMENDED)

```bash
# On production server
cd /path/to/chatbot_backend
git pull origin main  # or your branch
```

**If using Docker:**
```bash
docker compose down
docker compose build web
docker compose up -d
docker logs chatbot-backend  # Check logs
```

**If using PM2:**
```bash
pm2 restart all
pm2 logs  # Check logs
```

**If using systemd:**
```bash
sudo systemctl restart your-service
sudo journalctl -u your-service -f  # Check logs
```

---

### Method 2: Direct File Upload (If no git)

1. **Copy the fixed file to your server:**
   ```bash
   # From your local machine
   scp services/langchain/engine.py user@api.bayshorecommunication.org:/path/to/chatbot_backend/services/langchain/
   ```

2. **Restart your application** (same as Method 1 above)

---

### Method 3: Test Locally First

Before deploying to production:

```bash
# On your local machine
cd chatbot_backend

# Start local server
docker compose up -d

# Test the endpoint
curl -X POST http://localhost:8000/api/chatbot/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test" \
  -d '{
    "question": "What services do you offer?",
    "session_id": "test-123"
  }'
```

If it works locally, deploy to production.

---

## Verify Production After Deploy

```bash
# Test your live API
curl -X POST https://api.bayshorecommunication.org/api/chatbot/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_ACTUAL_API_KEY" \
  -d '{
    "question": "test",
    "session_id": "test-123"
  }'
```

**Should return:** A proper answer (not the 500 error)

---

## Check Logs After Deploy

Look for one of these messages:

**Good (New Langchain):**
```
✅ QA chain initialized (new API)
```

**Good (Old Langchain):**
```
[INFO] Using legacy langchain chains
✅ QA chain initialized (legacy API)
```

**Bad (Still failing):**
```
Error importing services: ...
```

---

## Still Getting Error?

If you still see the 500 error after deploying:

1. **Check if code was actually updated:**
   ```bash
   # On production server
   grep -n "USE_NEW_CHAINS" /path/to/chatbot_backend/services/langchain/engine.py
   ```
   Should show the new backward compatibility code.

2. **Check application was restarted:**
   ```bash
   # Check process start time (should be recent)
   ps aux | grep uvicorn  # or your app name
   ```

3. **Check logs for the actual error:**
   ```bash
   docker logs chatbot-backend --tail 100  # if Docker
   pm2 logs --lines 100  # if PM2
   tail -f /var/log/your-app.log  # if systemd
   ```

4. **Share the logs with me** - I'll help debug further!

