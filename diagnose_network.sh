#!/bin/bash

# Network Diagnostics for Email Issues
echo "🔍 NETWORK DIAGNOSTICS FOR EMAIL SENDING"
echo "========================================"
echo ""

# 1. Check container network mode
echo "1️⃣ Container Network Configuration:"
docker inspect chatbot-backend --format='{{.HostConfig.NetworkMode}}' 2>/dev/null || echo "❌ Container not running"
echo ""

# 2. Check DNS configuration
echo "2️⃣ DNS Configuration in Container:"
docker exec chatbot-backend cat /etc/resolv.conf 2>/dev/null || echo "❌ Cannot read DNS config"
echo ""

# 3. Test DNS resolution
echo "3️⃣ DNS Resolution Test:"
docker exec chatbot-backend getent hosts smtp.gmail.com 2>/dev/null || echo "❌ DNS resolution failed"
echo ""

# 4. Check iptables rules (host level)
echo "4️⃣ Firewall Rules (may require sudo):"
sudo iptables -L -n | grep -i docker | head -20 2>/dev/null || echo "⚠️  Cannot check iptables (may need sudo)"
echo ""

# 5. Test SMTP connectivity with Python
echo "5️⃣ Testing SMTP Connection with Python:"
docker exec chatbot-backend python3 -c "
import socket
import ssl
try:
    # Test DNS resolution
    ip = socket.gethostbyname('smtp.gmail.com')
    print(f'✅ DNS Resolution: smtp.gmail.com -> {ip}')
    
    # Test TCP connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('smtp.gmail.com', 465))
    print('✅ TCP Connection: Port 465 reachable')
    
    # Test SSL handshake
    context = ssl.create_default_context()
    ssock = context.wrap_socket(sock, server_hostname='smtp.gmail.com')
    print('✅ SSL Handshake: Successful')
    print(f'   Protocol: {ssock.version()}')
    ssock.close()
    
except socket.gaierror as e:
    print(f'❌ DNS Error: {e}')
except socket.timeout:
    print('❌ Connection Timeout: Cannot reach smtp.gmail.com:465')
except ConnectionRefusedError:
    print('❌ Connection Refused: Port 465 blocked')
except ssl.SSLError as e:
    print(f'❌ SSL Error: {e}')
except Exception as e:
    print(f'❌ Error: {e}')
" 2>/dev/null || echo "❌ Python test failed"
echo ""

# 6. Check Docker network settings
echo "6️⃣ Docker Network Details:"
docker network inspect $(docker inspect chatbot-backend --format='{{.HostConfig.NetworkMode}}' 2>/dev/null) --format='{{json .IPAM.Config}}' 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "❌ Cannot inspect network"
echo ""

# 7. Check if IP forwarding is enabled
echo "7️⃣ IP Forwarding (Host Level):"
cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo "❌ Cannot check IP forwarding"
echo "(Should be 1 for Docker networking to work)"
echo ""

# 8. Check routes in container
echo "8️⃣ Container Routing Table:"
docker exec chatbot-backend ip route 2>/dev/null || docker exec chatbot-backend route -n 2>/dev/null || echo "❌ Cannot check routes"
echo ""

echo "========================================"
echo "🏁 Diagnostics Complete"
echo ""
echo "COMMON ISSUES:"
echo "  • DNS resolution failed → Check DNS settings (8.8.8.8, 8.8.4.4)"
echo "  • TCP connection timeout → Check firewall/iptables rules"
echo "  • IP forwarding disabled → Run: sudo sysctl -w net.ipv4.ip_forward=1"
echo "  • Network unreachable → Check Docker network driver settings"
