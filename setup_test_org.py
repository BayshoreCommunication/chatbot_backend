#!/usr/bin/env python3
"""
Setup Test Organization Script
Creates a test organization with proper API key for testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database import create_organization
import uuid

def setup_test_organization():
    """Create a test organization for comprehensive testing"""
    
    # Test organization data
    org_data = {
        'name': 'Carter Injury Law Test',
        'email': 'test@carterinjurylaw.com',
        'phone': '(813) 922-0228',
        'address': '3114 N. Boulevard, Tampa, FL 33603',
        'website': 'https://www.carterinjurylaw.com',
        'industry': 'Legal Services',
        'description': 'Premier personal injury law firm in Tampa, Florida specializing in car accidents, slip and fall cases, medical malpractice, and workers compensation.',
        'pinecone_namespace': f'carter_test_{uuid.uuid4().hex[:8]}'
    }
    
    try:
        print("🏗️  Creating test organization...")
        result = create_organization(org_data)
        
        if result and 'api_key' in result:
            print("✅ Test organization created successfully!")
            print(f"📋 Organization ID: {result.get('id')}")
            print(f"🔑 API Key: {result.get('api_key')}")
            print(f"🏢 Organization Name: {result.get('name')}")
            print(f"🔖 Pinecone Namespace: {result.get('pinecone_namespace')}")
            
            # Save API key to a file for easy access
            with open('test_api_key.txt', 'w') as f:
                f.write(result.get('api_key'))
            
            print("\n💾 API key saved to: test_api_key.txt")
            print("\n🎯 You can now use this API key for testing:")
            print(f"   export TEST_API_KEY={result.get('api_key')}")
            
            return result.get('api_key')
        else:
            print("❌ Failed to create test organization")
            print(f"Result: {result}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating test organization: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    api_key = setup_test_organization()
    if api_key:
        print("\n🚀 Ready for testing! Run: python test_chatbot_comprehensive.py")
    else:
        print("\n💥 Setup failed. Please check the error messages above.")
        sys.exit(1)

