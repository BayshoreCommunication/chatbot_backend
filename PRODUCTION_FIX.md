# Fix Production Server - ask_bot Import Error

## Problem

Your live server at `https://api.bayshorecommunication.org` is returning:

```json
{
  "error": "500: Chatbot services are not available",
  "error_type": "HTTPException"
}
```

This means `SERVICES_AVAILABLE = False` because the `ask_bot` import is failing.

## Root Cause

Your production server has **OLD langchain packages** that don't support the new imports:

- Old: `from langchain.chains.question_answering import load_qa_chain` ❌ (deprecated)
- New: `from langchain.chains.combine_documents import create_stuff_documents_chain` ✅

## Quick Fix - SSH into Your Production Server

### Option 1: Manual Commands (SSH)

```bash
# SSH into your production server
ssh your-user@api.bayshorecommunication.org

# Navigate to your backend directory
cd /path/to/chatbot_backend

# Update langchain packages
pip install --upgrade -r requirements.txt

# Test the import
python3 -c "from services.langchain.engine import ask_bot; print('SUCCESS!')"

# Restart your application
# Choose one based on how you run the app:
sudo systemctl restart your-service-name
# OR
docker compose restart web
# OR
pm2 restart all
# OR
supervisorctl restart your-app
```

### Option 2: Using the Update Script

```bash
# On your production server
cd /path/to/chatbot_backend
chmod +x update_production.sh
./update_production.sh
```

### Option 3: Docker Deployment

If you're using Docker on production:

```bash
# SSH into production server
ssh your-user@api.bayshorecommunication.org

# Navigate to backend directory
cd /path/to/chatbot_backend

# Pull latest code
git pull origin main  # or your branch name

# Rebuild and restart containers
docker compose down
docker compose build --no-cache web
docker compose up -d

# Check logs
docker logs chatbot-backend
```

## Verify the Fix

After updating, test your API:

```bash
curl -X POST https://api.bayshorecommunication.org/api/chatbot/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "question": "What services do you offer?",
    "session_id": "test-123",
    "mode": "faq"
  }'
```

You should get a proper response instead of the error.

## Check Server Logs

To see the actual import error on your server:

```bash
# If using systemd
sudo journalctl -u your-service-name -n 100

# If using Docker
docker logs chatbot-backend --tail 100

# If using PM2
pm2 logs your-app --lines 100

# Or check application logs
tail -f /var/log/your-app/error.log
```

Look for lines like:

- "Error importing services: ..."
- "ModuleNotFoundError: No module named 'langchain.chains.combine_documents'"
- Any langchain-related errors

## Required Package Versions

Your `requirements.txt` should have:

```txt
langchain>=0.3.18
langchain-core>=0.3.33
langchain-openai>=0.2.14
langchain-community>=0.3.17
langchain-pinecone>=0.2.0
pinecone-client==5.0.1
openai==1.58.1
```

## Troubleshooting

### If import still fails after update:

1. **Check Python version**

   ```bash
   python3 --version  # Should be 3.9+
   ```

2. **Check if packages installed correctly**

   ```bash
   pip list | grep langchain
   ```

3. **Test import directly**

   ```bash
   python3 -c "from langchain.chains.combine_documents import create_stuff_documents_chain; print('OK')"
   ```

4. **Check for pip cache issues**

   ```bash
   pip cache purge
   pip install --upgrade --force-reinstall -r requirements.txt
   ```

5. **Check virtual environment** (if using one)
   ```bash
   which python3
   which pip
   # Make sure you're using the right venv
   ```

## Need Help?

If the issue persists:

1. Send me the output of:

   ```bash
   pip list | grep langchain
   python3 -c "from services.langchain.engine import ask_bot" 2>&1
   ```

2. Send the server logs showing the import error

3. Confirm:
   - How is your app deployed? (Docker, systemd, PM2, etc.)
   - Where is the app located on the server?
   - How do you restart it?
