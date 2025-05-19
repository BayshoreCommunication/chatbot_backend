import requests
import json
import sys

# Server URL
BASE_URL = "http://127.0.0.1:8000"

def test_organization_isolation():
    """Test that each organization has isolated data in their namespace"""
    print("Testing multi-tenant data isolation...\n")
    
    # Step 1: Create two different organizations
    print("Step 1: Creating two test organizations...")
    
    # Create first organization
    org1_data = {
        "name": "Legal Services Inc.",
        "subscription_tier": "standard"
    }
    
    # Create second organization
    org2_data = {
        "name": "Marketing Solutions LLC",
        "subscription_tier": "standard"
    }
    
    try:
        # Register org1
        response = requests.post(f"{BASE_URL}/organization/register", json=org1_data)
        response.raise_for_status()
        org1_result = response.json()
        
        print(f"Organization 1 registered: {org1_result['organization']['name']}")
        print(f"API Key 1: {org1_result['organization']['api_key']}")
        print(f"Namespace 1: {org1_result['organization']['pinecone_namespace']}\n")
        
        api_key1 = org1_result['organization']['api_key']
        
        # Register org2
        response = requests.post(f"{BASE_URL}/organization/register", json=org2_data)
        response.raise_for_status()
        org2_result = response.json()
        
        print(f"Organization 2 registered: {org2_result['organization']['name']}")
        print(f"API Key 2: {org2_result['organization']['api_key']}")
        print(f"Namespace 2: {org2_result['organization']['pinecone_namespace']}\n")
        
        api_key2 = org2_result['organization']['api_key']
    except Exception as e:
        print(f"Error registering organizations: {str(e)}")
        sys.exit(1)
    
    # Step 2: Upload different documents to each organization
    print("Step 2: Uploading different documents to each organization...")
    
    # Document for org1 - legal services
    legal_text = """
    Legal Services Inc. provides high-quality legal consultation services.
    Our services include:
    - Contract review and drafting
    - Litigation support
    - Corporate law
    - Intellectual property
    - Estate planning
    
    Contact us at contact@legalservices.example.com or call 555-123-4567.
    """
    
    # Document for org2 - marketing services
    marketing_text = """
    Marketing Solutions LLC specializes in digital marketing strategies.
    Our services include:
    - Social media management
    - SEO optimization
    - Content creation
    - Email marketing
    - PPC advertising
    
    Contact us at hello@marketingsolutions.example.com or call 555-987-6543.
    """
    
    try:
        # Upload to org1
        response = requests.post(
            f"{BASE_URL}/chatbot/upload_document", 
            headers={"X-API-Key": api_key1},
            data={"text": legal_text}
        )
        response.raise_for_status()
        upload_result1 = response.json()
        
        print(f"Org1 document upload: {upload_result1['status']}")
        
        # Upload to org2
        response = requests.post(
            f"{BASE_URL}/chatbot/upload_document", 
            headers={"X-API-Key": api_key2},
            data={"text": marketing_text}
        )
        response.raise_for_status()
        upload_result2 = response.json()
        
        print(f"Org2 document upload: {upload_result2['status']}\n")
    except Exception as e:
        print(f"Error uploading documents: {str(e)}")
        sys.exit(1)
    
    # Step 3: Ask the same question to both organizations and verify different answers
    print("Step 3: Testing data isolation by asking the same question to both organizations...\n")
    question = "What services do you offer?"
    
    try:
        # Ask org1
        print(f"Asking Organization 1 ({org1_data['name']}): '{question}'")
        response = requests.post(
            f"{BASE_URL}/chatbot/ask",
            headers={"X-API-Key": api_key1, "Content-Type": "application/json"},
            json={
                "question": question,
                "session_id": "test_session_org1",
                "mode": "faq",
                "user_data": {"name": "Test User", "email": "testuser@example.com"}
            }
        )
        response.raise_for_status()
        answer1 = response.json()['answer']
        
        print(f"Organization 1 answer: {answer1}\n")
        
        # Ask org2
        print(f"Asking Organization 2 ({org2_data['name']}): '{question}'")
        response = requests.post(
            f"{BASE_URL}/chatbot/ask",
            headers={"X-API-Key": api_key2, "Content-Type": "application/json"},
            json={
                "question": question,
                "session_id": "test_session_org2",
                "mode": "faq",
                "user_data": {"name": "Test User", "email": "testuser@example.com"}
            }
        )
        response.raise_for_status()
        answer2 = response.json()['answer']
        
        print(f"Organization 2 answer: {answer2}\n")
        
        # Analyze results
        if "legal" in answer1.lower() and "contract" in answer1.lower() and "marketing" not in answer1.lower():
            print("✅ Organization 1 correctly returned legal services information")
        else:
            print("❌ Organization 1 might be using cross-contaminated data")
        
        if "marketing" in answer2.lower() and "social media" in answer2.lower() and "legal" not in answer2.lower():
            print("✅ Organization 2 correctly returned marketing services information")
        else:
            print("❌ Organization 2 might be using cross-contaminated data")
            
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        sys.exit(1)
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_organization_isolation() 