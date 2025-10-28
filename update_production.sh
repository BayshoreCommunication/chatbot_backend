#!/bin/bash
# Production Server Update Script
# Run this on your production server to fix the langchain import issues

echo "=========================================="
echo "Production Server Package Update"
echo "=========================================="

# Step 1: Check current langchain version
echo ""
echo "1. Checking current langchain packages..."
pip list | grep langchain || echo "Langchain packages not found"

# Step 2: Upgrade packages
echo ""
echo "2. Upgrading langchain packages..."
pip install --upgrade \
    "langchain>=0.3.18" \
    "langchain-core>=0.3.33" \
    "langchain-openai>=0.2.14" \
    "langchain-community>=0.3.17" \
    "langchain-pinecone>=0.2.0" \
    "pinecone-client==5.0.1" \
    "openai==1.58.1"

# Step 3: Verify installation
echo ""
echo "3. Verifying new package versions..."
pip list | grep langchain

# Step 4: Test import
echo ""
echo "4. Testing ask_bot import..."
python3 << 'PYEOF'
try:
    from services.langchain.engine import ask_bot
    print("✅ SUCCESS: ask_bot imported successfully!")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "=========================================="
echo "5. Restart your application server:"
echo "   - If using systemd: sudo systemctl restart your-service"
echo "   - If using Docker: docker compose restart web"
echo "   - If using PM2: pm2 restart all"
echo "=========================================="

