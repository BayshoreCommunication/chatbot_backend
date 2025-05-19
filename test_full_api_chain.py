import requests
import json
import os
import time
from dotenv import load_dotenv
load_dotenv()

# Set the correct dimension for Pinecone
os.environ["PINECONE_DIMENSION"] = "1024"

# Server URL
BASE_URL = "http://127.0.0.1:8000"

def test_full_api_chain():
    """Test the full API chain from organization registration to document upload and retrieval"""
    print("Testing full API chain for multi-tenant vector store...")
    
    # Step 1: Register a new organization
    print("\nStep 1: Registering a new organization...")
    org_data = {
        "name": "Full Chain Test Org",
        "subscription_tier": "standard"
    }
    
    response = requests.post(f"{BASE_URL}/organization/register", json=org_data)
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return
    
    org_result = response.json()
    api_key = org_result['organization']['api_key']
    namespace = org_result['organization']['pinecone_namespace']
    
    print(f"Organization registered: {org_result['organization']['name']}")
    print(f"API Key: {api_key}")
    print(f"Namespace: {namespace}")
    
    # Step 2: Upload a document with distinct text
    print("\nStep 2: Uploading a document...")
    unique_text = f"""
    This is a document specifically for the Full Chain Test Org.
    
    This organization helps test the complete API flow.
    
    Our unique identifier is: API-CHAIN-TEST-12345
    
    Our motto is: "Testing the full API chain for vector storage and retrieval."
    
    Contact us at: info@fullchaintest.example.com
    """
    
    response = requests.post(
        f"{BASE_URL}/chatbot/upload_document", 
        headers={"X-API-Key": api_key},
        data={"text": unique_text}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return
    
    upload_result = response.json()
    print(f"Document upload result: {upload_result['status']}")
    print(f"Documents added: {upload_result.get('documents_added', 0)}")
    
    # Step 3: Wait a bit for indexing
    print("\nStep 3: Waiting for indexing...")
    time.sleep(3)
    
    # Step 4: Retrieve document content by asking a specific question
    print("\nStep 4: Retrieving document content...")
    unique_id = "API-CHAIN-TEST-12345"
    
    # Ask different variations of the question to test retrieval
    questions = [
        "What is our unique identifier?",
        "Tell me the unique identifier",
        "What is API-CHAIN-TEST?",
        "What is our motto?",
        "Do you know our unique identifier?"
    ]
    
    for idx, question in enumerate(questions):
        print(f"\nQuestion {idx+1}: {question}")
        
        response = requests.post(
            f"{BASE_URL}/chatbot/ask",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "question": question,
                "session_id": f"test_session_{idx}",
                "mode": "faq",
                "user_data": {"name": "Test User", "email": "test@example.com"}
            }
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            continue
        
        ask_result = response.json()
        print(f"Answer: {ask_result['answer']}")
        
        # Check if the answer contains key information
        if unique_id in ask_result['answer']:
            print(f"✅ SUCCESS: Answer contains the unique identifier!")
        elif "motto" in question.lower() and "full API chain" in ask_result['answer']:
            print(f"✅ SUCCESS: Answer contains information about the motto!")
    
    print("\nTest completed.")

if __name__ == "__main__":
    test_full_api_chain() 