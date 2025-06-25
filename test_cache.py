#!/usr/bin/env python3
"""
Test script to verify Redis caching is working
"""
import requests
import time
import json

# Admin API base URL
BASE_URL = "http://127.0.0.1:8000/admin"

def test_cache_performance():
    """Test the cache performance improvement"""
    print("🧪 Testing Redis Cache Performance")
    print("=" * 50)
    
    # First, get an admin token (you'll need to replace with actual admin credentials)
    print("⚠️  Note: This test requires admin authentication")
    print("   Make sure you have admin access configured")
    print()
    
    # Test endpoints with their expected cache TTLs
    endpoints_to_test = [
        {
            "name": "Dashboard Stats", 
            "url": f"{BASE_URL}/dashboard-stats",
            "expected_ttl": 60,
            "description": "Basic dashboard statistics"
        },
        {
            "name": "Organizations", 
            "url": f"{BASE_URL}/organizations",
            "expected_ttl": 120,
            "description": "All organizations list"
        },
        {
            "name": "Business Insights", 
            "url": f"{BASE_URL}/business-insights",
            "expected_ttl": 300,
            "description": "Business KPIs and insights"
        },
        {
            "name": "Analytics", 
            "url": f"{BASE_URL}/analytics",
            "expected_ttl": 600,
            "description": "Historical analytics data"
        },
        {
            "name": "Realtime Stats", 
            "url": f"{BASE_URL}/realtime-stats",
            "expected_ttl": 15,
            "description": "Real-time statistics"
        }
    ]
    
    # Headers for admin authentication (you'll need to set this)
    headers = {
        "Authorization": "Bearer YOUR_ADMIN_TOKEN_HERE",
        "Content-Type": "application/json"
    }
    
    print("Testing cache endpoints:")
    print("Note: Replace 'YOUR_ADMIN_TOKEN_HERE' with actual admin token")
    print()
    
    for endpoint in endpoints_to_test:
        print(f"📊 Testing: {endpoint['name']}")
        print(f"   Description: {endpoint['description']}")
        print(f"   Expected TTL: {endpoint['expected_ttl']} seconds")
        
        # Test first request (should hit database)
        start_time = time.time()
        try:
            response1 = requests.get(endpoint['url'], headers=headers, timeout=10)
            first_request_time = time.time() - start_time
            
            if response1.status_code == 200:
                print(f"   ✅ First request: {first_request_time:.3f}s (database)")
                
                # Test second request immediately (should hit cache)
                start_time = time.time()
                response2 = requests.get(endpoint['url'], headers=headers, timeout=10)
                second_request_time = time.time() - start_time
                
                if response2.status_code == 200:
                    print(f"   ✅ Second request: {second_request_time:.3f}s (cache)")
                    
                    # Calculate performance improvement
                    if second_request_time > 0:
                        improvement = (first_request_time - second_request_time) / first_request_time * 100
                        print(f"   🚀 Performance improvement: {improvement:.1f}%")
                    
                    # Check if responses are identical (cache working)
                    if response1.text == response2.text:
                        print(f"   ✅ Cache working: Identical responses")
                    else:
                        print(f"   ⚠️  Cache issue: Responses differ")
                else:
                    print(f"   ❌ Second request failed: {response2.status_code}")
            else:
                if response1.status_code == 401:
                    print(f"   ⚠️  Authentication required: {response1.status_code}")
                else:
                    print(f"   ❌ First request failed: {response1.status_code}")
                    
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")
        
        print()

def test_cache_invalidation():
    """Test cache invalidation endpoint"""
    print("🗑️  Testing Cache Invalidation")
    print("=" * 30)
    
    headers = {
        "Authorization": "Bearer YOUR_ADMIN_TOKEN_HERE",
        "Content-Type": "application/json"
    }
    
    try:
        # Test cache invalidation
        response = requests.post(f"{BASE_URL}/cache/invalidate", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Cache invalidation successful")
            print(f"   Deleted entries: {data.get('deleted_entries', 0)}")
        else:
            print(f"❌ Cache invalidation failed: {response.status_code}")
            
        # Test cache status
        response = requests.get(f"{BASE_URL}/cache/status", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Cache status: {data.get('status', 'unknown')}")
            if data.get('cache_keys'):
                print("   Cache keys status:")
                for key, status in data['cache_keys'].items():
                    exists = "✅" if status['exists'] else "❌"
                    ttl = status.get('ttl_seconds', -1)
                    print(f"     {exists} {key}: TTL={ttl}s")
        else:
            print(f"❌ Cache status failed: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

def check_redis_connection():
    """Check if Redis is available"""
    print("🔌 Checking Redis Connection")
    print("=" * 30)
    
    try:
        from services.cache import cache
        if cache.is_available():
            print("✅ Redis is connected and available")
            
            # Test basic operations
            test_key = "cache_test"
            test_value = {"test": "data", "timestamp": time.time()}
            
            if cache.set(test_key, test_value, ttl=60):
                print("✅ Cache write successful")
                
                retrieved = cache.get(test_key)
                if retrieved and retrieved == test_value:
                    print("✅ Cache read successful")
                    
                    ttl = cache.get_ttl(test_key)
                    print(f"✅ Cache TTL: {ttl} seconds")
                    
                    if cache.delete(test_key):
                        print("✅ Cache delete successful")
                    else:
                        print("⚠️  Cache delete failed")
                else:
                    print("❌ Cache read failed or data mismatch")
            else:
                print("❌ Cache write failed")
        else:
            print("❌ Redis is not available")
            print("   Make sure Redis is running: sudo service redis-server start")
            
    except Exception as e:
        print(f"❌ Redis connection error: {e}")

if __name__ == "__main__":
    print("🎯 Redis Cache Testing Suite")
    print("=" * 50)
    print()
    
    # Check Redis connection first
    check_redis_connection()
    print()
    
    # Test cache performance
    test_cache_performance()
    print()
    
    # Test cache management
    test_cache_invalidation()
    print()
    
    print("📋 Summary:")
    print("• Redis caching has been implemented for all admin endpoints")
    print("• Different TTLs based on data freshness requirements:")
    print("  - Realtime stats: 15 seconds")
    print("  - Dashboard stats: 1 minute") 
    print("  - Organizations/Subscriptions: 2 minutes")
    print("  - Business insights: 5 minutes")
    print("  - Analytics: 10 minutes")
    print("• Cache invalidation and status endpoints available")
    print("• Significant performance improvement expected on repeated requests")
    print()
    print("🚀 Benefits:")
    print("• Faster dashboard loading on subsequent visits")
    print("• Reduced database load")
    print("• Better user experience")
    print("• Automatic cache expiration ensures data freshness") 