# Fix: Network Unreachable Error for Email Sending

## Problem

```
❌ Failed to send email to arsahak.bayshore@gmail.com: [Errno 101] Network unreachable
```

The Docker container **cannot reach external SMTP servers** due to network configuration issues.

---

## Root Cause

1. **Missing network configuration** in `docker-compose.yml`
2. **No DNS servers** configured for container
3. Possible **IP forwarding disabled** on host
4. Possible **firewall rules** blocking outbound SMTP connections

---

## Solution Applied

### 1. Updated `docker-compose.yml`

Added proper network configuration:

```yaml
# DNS servers for external connectivity
dns:
  - 8.8.8.8
  - 8.8.4.4

# Network configuration at bottom of file
networks:
  default:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_ip_masquerade: "true"
      com.docker.network.driver.mtu: "1500"
```

---

## Deployment Steps

### Option A: Automatic Fix (Recommended)

**On Linux/Mac:**

```bash
cd chatbot_backend
chmod +x fix_network.sh
./fix_network.sh
```

**On Windows:**

```cmd
cd chatbot_backend
fix_network.bat
```

### Option B: Manual Fix

```bash
# 1. Stop containers
docker-compose down

# 2. Clean up networks
docker network prune -f

# 3. Rebuild with new configuration
docker-compose up -d --build

# 4. Wait for startup
sleep 10

# 5. Check status
docker-compose ps
```

---

## Verification

### Test Network Connectivity

Run diagnostics:

```bash
chmod +x diagnose_network.sh
./diagnose_network.sh
```

Expected output:

```
✅ DNS Resolution: smtp.gmail.com -> 142.250.xxx.xxx
✅ TCP Connection: Port 465 reachable
✅ SSL Handshake: Successful
```

### Test Email Sending

1. Create a new test subscription in the application
2. Check logs:
   ```bash
   docker logs chatbot-backend --tail 50 | grep -i email
   ```

Expected logs:

```
✅ Confirmation email sent successfully to user@example.com
```

---

## If Still Not Working

### Check Host-Level IP Forwarding

```bash
# Check current status
cat /proc/sys/net/ipv4/ip_forward

# If it shows 0, enable it:
sudo sysctl -w net.ipv4.ip_forward=1

# Make permanent (add to /etc/sysctl.conf):
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
```

### Check Firewall Rules

```bash
# Check if UFW is blocking outbound connections
sudo ufw status

# Allow outbound SMTP (if needed)
sudo ufw allow out 465/tcp
sudo ufw allow out 587/tcp
```

### Check iptables Rules

```bash
# Check Docker iptables rules
sudo iptables -L DOCKER -n -v

# Check FORWARD chain
sudo iptables -L FORWARD -n -v

# If needed, allow SMTP:
sudo iptables -I DOCKER-USER -p tcp --dport 465 -j ACCEPT
sudo iptables -I DOCKER-USER -p tcp --dport 587 -j ACCEPT
```

### Alternative: Use Host Network Mode (Not Recommended for Production)

If nothing else works, temporarily test with host networking:

```yaml
# In docker-compose.yml, add to web service:
network_mode: "host"
```

⚠️ **Warning:** Host mode removes container isolation and may cause port conflicts.

---

## Test from Inside Container

```bash
# Enter container
docker exec -it chatbot-backend bash

# Test DNS
nslookup smtp.gmail.com

# Test SMTP port
telnet smtp.gmail.com 465

# Test with curl
curl -v telnet://smtp.gmail.com:465

# Test with Python
python3 -c "
import smtplib
import ssl
context = ssl.create_default_context()
server = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context)
server.login('bayshoreai@gmail.com', 'your-app-password')
print('✅ SMTP connection successful!')
server.quit()
"
```

---

## Summary

✅ **Changes Made:**

- Added DNS configuration (8.8.8.8, 8.8.4.4)
- Configured proper bridge network with IP masquerading
- Created automated fix scripts

🚀 **Next Steps:**

1. Run `fix_network.sh` (Linux/Mac) or `fix_network.bat` (Windows)
2. Wait for containers to restart
3. Test email by creating new subscription
4. Check logs for success message

📧 **Expected Result:**
Email notifications will now work correctly on production server.
