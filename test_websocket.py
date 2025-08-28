#!/usr/bin/env python3
"""
WebSocket Test Script for Chatbot Backend
Tests both Socket.IO and native WebSocket functionality
"""

import asyncio
import websockets
import socketio
import requests
import json
import time
from urllib.parse import urljoin

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your server URL
API_KEY = "your-api-key"  # Replace with actual API key

class WebSocketTester:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.sio = socketio.AsyncClient()
        
    async def test_health_endpoints(self):
        """Test health check endpoints"""
        print("🔍 Testing Health Endpoints...")
        
        try:
            # Test /healthz
            response = requests.get(f"{self.base_url}/healthz")
            print(f"✅ /healthz: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"❌ /healthz failed: {e}")
            
        try:
            # Test /health
            response = requests.get(f"{self.base_url}/health")
            print(f"✅ /health: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"❌ /health failed: {e}")
            
    async def test_native_websocket(self):
        """Test native WebSocket endpoint"""
        print("\n🔌 Testing Native WebSocket...")
        
        try:
            ws_url = f"ws://{self.base_url.replace('http://', '').replace('https://', '')}/ws"
            print(f"Connecting to: {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                print("✅ Connected to native WebSocket")
                
                # Send test message
                test_message = "Hello from test script!"
                await websocket.send(test_message)
                print(f"📤 Sent: {test_message}")
                
                # Receive response
                response = await websocket.recv()
                print(f"📥 Received: {response}")
                
                # Send another message
                await websocket.send("Test message 2")
                response2 = await websocket.recv()
                print(f"📥 Received: {response2}")
                
                print("✅ Native WebSocket test completed successfully")
                
        except Exception as e:
            print(f"❌ Native WebSocket test failed: {e}")
            
    async def test_socketio(self):
        """Test Socket.IO connection"""
        print("\n🔌 Testing Socket.IO...")
        
        try:
            # Connect to Socket.IO
            await self.sio.connect(
                self.base_url,
                transports=['websocket', 'polling'],
                query={'apiKey': self.api_key}
            )
            print("✅ Connected to Socket.IO")
            
            # Wait for connection confirmation
            await asyncio.sleep(2)
            
            # Test room joining
            await self.sio.emit('join_room', {'room': 'test-room'})
            print("📤 Sent join_room event")
            
            # Wait for response
            await asyncio.sleep(1)
            
            # Disconnect
            await self.sio.disconnect()
            print("✅ Socket.IO test completed successfully")
            
        except Exception as e:
            print(f"❌ Socket.IO test failed: {e}")
            
    async def test_api_endpoints(self):
        """Test API endpoints that use WebSocket"""
        print("\n🌐 Testing API Endpoints...")
        
        headers = {"X-API-Key": self.api_key}
        
        try:
            # Test socket health endpoint
            response = requests.get(f"{self.base_url}/api/chatbot/socket-health", headers=headers)
            print(f"✅ Socket health: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"❌ Socket health failed: {e}")
            
        try:
            # Test main API endpoint
            response = requests.get(f"{self.base_url}/", headers=headers)
            print(f"✅ Main API: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"❌ Main API failed: {e}")
            
    async def run_all_tests(self):
        """Run all WebSocket tests"""
        print("🚀 Starting WebSocket Tests...")
        print(f"Target URL: {self.base_url}")
        print(f"API Key: {self.api_key[:10]}..." if self.api_key != "your-api-key" else "API Key: Not set")
        print("=" * 50)
        
        # Test health endpoints
        await self.test_health_endpoints()
        
        # Test native WebSocket
        await self.test_native_websocket()
        
        # Test Socket.IO
        await self.test_socketio()
        
        # Test API endpoints
        await self.test_api_endpoints()
        
        print("\n" + "=" * 50)
        print("🎉 WebSocket testing completed!")

async def main():
    """Main test function"""
    # Configuration
    base_url = input(f"Enter server URL (default: {BASE_URL}): ").strip() or BASE_URL
    api_key = input(f"Enter API key (default: {API_KEY}): ").strip() or API_KEY
    
    # Create tester and run tests
    tester = WebSocketTester(base_url, api_key)
    await tester.run_all_tests()

if __name__ == "__main__":
    # Run the tests
    asyncio.run(main())
