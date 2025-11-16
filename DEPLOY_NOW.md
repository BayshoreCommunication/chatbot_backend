# 🚨 URGENT: Deploy Network Fix to Production Server

## Current Status

❌ **Email still failing with:** `[Errno 101] Network unreachable`
✅ **Webhooks working correctly** (receiving events from Stripe)
✅ **Fix ready** (docker-compose.yml updated with DNS + network config)
⏳ **Fix NOT deployed yet** (changes only in local repo)

---

## Deploy to Production Server NOW

### Step 1: Commit and Push Changes

**On your local machine (Windows):**

```cmd
cd d:\bayai-chatbot\chatbot_backend

git add docker-compose.yml fix_network.sh fix_network.bat diagnose_network.sh NETWORK_FIX.md EMAIL_FIX_SUMMARY.md

git commit -m "fix: add DNS and network config to resolve email sending error"

git push origin main
```

### Step 2: Deploy on Production Server

**SSH to your Digital Ocean server:**

```bash
ssh root@68.183.227.9
# OR
ssh your-username@68.183.227.9
```

**Once logged in, run these commands:**

```bash
# Navigate to project directory
cd /root/chatbot_backend
# OR wherever your project is located

# Pull latest changes
git pull origin main

# Stop current containers
docker-compose down

# Remove old networks
docker network prune -f

# Rebuild and restart with new network configuration
docker-compose up -d --build

# Wait for containers to start
sleep 15

# Check status
docker-compose ps

# Verify network connectivity
docker exec chatbot-backend nslookup smtp.gmail.com

# Follow logs to see if email works
docker logs chatbot-backend --follow
```

### Step 3: Test Email Sending

1. Create a new test subscription in your application
2. Watch the logs in real-time:
   ```bash
   docker logs chatbot-backend --follow | grep -i email
   ```

3. Look for this SUCCESS message:
   ```
   ✅ Confirmation email sent successfully to user@example.com
   ```

---

## Quick Copy-Paste Commands for Production

**All commands in one block (copy and paste):**

```bash
cd /root/chatbot_backend && \
git pull origin main && \
docker-compose down && \
docker network prune -f && \
docker-compose up -d --build && \
sleep 15 && \
docker-compose ps && \
echo "Testing network connectivity..." && \
docker exec chatbot-backend nslookup smtp.gmail.com && \
echo "✅ Deployment complete! Now test email by creating a subscription."
```

---

## What the Fix Does

The updated `docker-compose.yml` adds:

1. **DNS servers** for container:
   ```yaml
   dns:
     - 8.8.8.8
     - 8.8.4.4
   ```

2. **Proper network configuration**:
   ```yaml
   networks:
     default:
       driver: bridge
       driver_opts:
         com.docker.network.bridge.enable_ip_masquerade: "true"
   ```

This allows the container to:
- ✅ Resolve DNS (smtp.gmail.com → IP address)
- ✅ Reach external SMTP servers (port 465)
- ✅ Send emails successfully

---

## Expected Results After Deployment

### Before Fix (Current):
```
🔌 Connecting to SMTP server...
❌ Failed to send email: [Errno 101] Network unreachable
```

### After Fix (Expected):
```
🔌 Connecting to SMTP server...
✅ SMTP connection established
✅ Confirmation email sent successfully to arsahak.bayshore@gmail.com
```

---

## Troubleshooting

### If you can't find the project directory:

```bash
# Search for docker-compose.yml
find / -name "docker-compose.yml" 2>/dev/null | grep chatbot

# OR search for the Dockerfile
find / -name "Dockerfile" 2>/dev/null | grep chatbot
```

### If git pull fails:

```bash
# Reset any local changes
git reset --hard HEAD

# Pull again
git pull origin main
```

### If docker-compose command not found:

```bash
# Use docker compose (without hyphen) on newer Docker versions
docker compose down
docker compose up -d --build
```

### If IP forwarding is disabled:

```bash
# Check
cat /proc/sys/net/ipv4/ip_forward

# If 0, enable it:
sudo sysctl -w net.ipv4.ip_forward=1

# Make permanent
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
```

---

## Verification Checklist

- [ ] Committed and pushed changes from local machine
- [ ] SSH'd to production server (68.183.227.9)
- [ ] Navigated to project directory
- [ ] Pulled latest changes (`git pull origin main`)
- [ ] Stopped containers (`docker-compose down`)
- [ ] Cleaned networks (`docker network prune -f`)
- [ ] Rebuilt containers (`docker-compose up -d --build`)
- [ ] Verified containers running (`docker-compose ps`)
- [ ] Tested DNS resolution (`docker exec chatbot-backend nslookup smtp.gmail.com`)
- [ ] Created test subscription
- [ ] Checked logs for success message
- [ ] Received email in inbox

---

## Support

If you encounter issues:

1. **Share full logs:**
   ```bash
   docker logs chatbot-backend --tail 100 > deployment_logs.txt
   ```

2. **Run diagnostics:**
   ```bash
   chmod +x diagnose_network.sh
   ./diagnose_network.sh > diagnostics.txt
   ```

3. **Check Docker version:**
   ```bash
   docker --version
   docker-compose --version
   ```

4. **Check firewall:**
   ```bash
   sudo ufw status
   sudo iptables -L -n | grep -i docker
   ```

---

## Time Estimate

⏱️ **Total deployment time:** 5-10 minutes

- Git push: 30 seconds
- SSH + navigate: 1 minute
- Pull + rebuild: 3-5 minutes
- Testing: 2-3 minutes

---

## Next Steps After Successful Deployment

1. ✅ Test subscription creation email
2. ✅ Test subscription cancellation email
3. ✅ Monitor logs for 24 hours
4. ✅ Document successful resolution

---

## Contact

If you need help with any step, share:
- Current directory (`pwd`)
- Git status (`git status`)
- Docker logs (`docker logs chatbot-backend --tail 50`)
- Error messages
