import requests
import json
import sys

# Server URL
BASE_URL = "http://127.0.0.1:8000"

def test_organization_vector_store():
    """Test the multi-tenant vector store functionality"""
    print("Testing multi-tenant vector store functionality...\n")
    
    # Step 1: Register a new organization
    print("Step 1: Registering a new organization...")
    org_data = {
        "name": "Test Organization",
        "subscription_tier": "standard"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/organization/register", json=org_data)
        response.raise_for_status()
        org_result = response.json()
        
        print(f"Organization registered: {org_result['organization']['name']}")
        print(f"API Key: {org_result['organization']['api_key']}")
        print(f"Namespace: {org_result['organization']['pinecone_namespace']}\n")
        
        api_key = org_result['organization']['api_key']
    except Exception as e:
        print(f"Error registering organization: {str(e)}")
        sys.exit(1)
    
    # Step 2: Upload a document to the organization's vector store
    print("Step 2: Uploading a document to the organization's vector store...")
    test_text = """
    This is a test document for our organization. 
    We provide legal services including contract review, litigation support, and compliance consulting.
    Our team of experienced attorneys specializes in corporate law, intellectual property, and employment law.
    Contact us at info@testorganization.com or call 555-123-4567.
    """
    
    try:
        response = requests.post(
            f"{BASE_URL}/chatbot/upload_document", 
            headers={"X-API-Key": api_key},
            data={"text": test_text}
        )
        response.raise_for_status()
        upload_result = response.json()
        
        print(f"Document upload result: {upload_result['status']}")
        if upload_result['status'] == 'success':
            print(f"Successfully added {upload_result.get('documents_added', 0)} document chunks\n")
        else:
            print(f"Error: {upload_result.get('message', 'Unknown error')}\n")
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        sys.exit(1)
    
    # Step 3: Ask a question that should be answered using the uploaded document
    print("Step 3: Asking a question about the uploaded document...")
    question = "What services does your organization provide?"
    
    try:
        response = requests.post(
            f"{BASE_URL}/chatbot/ask",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "question": question,
                "session_id": "test_session_1",
                "mode": "faq",
                "user_data": {"name": "Tester", "email": "tester@example.com"}
            }
        )
        response.raise_for_status()
        ask_result = response.json()
        
        print(f"Question: {question}")
        print(f"Answer: {ask_result['answer']}\n")
    except Exception as e:
        print(f"Error asking question: {str(e)}")
        sys.exit(1)
    
    # Step 4: Check organization usage statistics
    print("Step 4: Checking organization usage statistics...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/organization/usage",
            headers={"X-API-Key": api_key}
        )
        response.raise_for_status()
        usage_result = response.json()
        
        print(f"API Calls: {usage_result['usage']['api_calls']}")
        print(f"Vector Embeddings: {usage_result['usage']['vector_embeddings']}")
        print(f"Storage Used: {usage_result['usage']['storage_used']} bytes\n")
    except Exception as e:
        print(f"Error checking usage: {str(e)}")
        sys.exit(1)
    
    print("Test completed successfully!")

if __name__ == "__main__":
    test_organization_vector_store() 