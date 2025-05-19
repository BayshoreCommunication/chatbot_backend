import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import requests
import json
import sys
from pprint import pprint

# Load environment variables
load_dotenv()

# Initialize OpenAI embeddings
openai_api_key = os.getenv("OPENAI_API_KEY")
embeddings = OpenAIEmbeddings(
    openai_api_key=openai_api_key,
    openai_api_base="https://api.openai.com/v1"
)

# Initialize Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX")

print(f"OpenAI API Key (truncated): {openai_api_key[:10]}...")
print(f"Pinecone API Key (truncated): {pinecone_api_key[:10]}...")
print(f"Index name: {index_name}")

pc = Pinecone(api_key=pinecone_api_key)

# List all indexes
print("Available indexes:")
indexes = pc.list_indexes()
existing_index_names = [index.name for index in indexes.indexes]
print(existing_index_names)

# Try to connect to the specific index
try:
    index = pc.Index(index_name)
    print(f"Successfully connected to index: {index_name}")
    
    # Create a simple document
    text = """This is a test document to check if document upload to Pinecone works correctly.
    It should be embedded and stored in the vector database.
    If you can find this text later through a similarity search, it means everything works!"""
    
    # Split the document
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_text(text)
    documents = [Document(page_content=doc) for doc in splits]
    
    print(f"Created {len(documents)} document chunks")
    
    # Store documents directly in Pinecone
    print(f"Storing documents in index: {index_name}")
    vectorstore = PineconeVectorStore.from_documents(
        documents=documents, 
        embedding=embeddings, 
        index=index,
        text_key="text"
    )
    
    print("Successfully stored documents in Pinecone!")
    
    # Try to retrieve the stored document
    print("\nTesting retrieval...")
    retrieved_docs = vectorstore.similarity_search("test document", k=1)
    
    if retrieved_docs:
        print(f"Successfully retrieved document: {retrieved_docs[0].page_content[:50]}...")
    else:
        print("No documents retrieved.")
    
except Exception as e:
    print(f"Error: {str(e)}")

# Server URL
BASE_URL = "http://127.0.0.1:8000"

def test_document_upload_and_retrieval():
    """Test uploading a document and retrieving its content for a specific organization"""
    print("Testing document upload and retrieval for an organization...\n")
    
    # Step 1: Create a test organization
    print("Step 1: Creating a test organization...")
    org_data = {
        "name": "Test Document Corp",
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
    
    # Step 2: Check current usage statistics
    print("Step 2: Checking initial usage statistics...")
    try:
        response = requests.get(
            f"{BASE_URL}/organization/usage",
            headers={"X-API-Key": api_key}
        )
        response.raise_for_status()
        usage_before = response.json()
        
        print(f"Initial vector count: {usage_before['usage']['vector_embeddings']}")
        print(f"Initial storage used: {usage_before['usage']['storage_used']} bytes\n")
    except Exception as e:
        print(f"Error checking usage: {str(e)}")
        sys.exit(1)
    
    # Step 3: Upload a unique document to the organization
    print("Step 3: Uploading a unique document...")
    unique_text = f"""
    Test Document Corp is a specialized document management company.
    
    Our unique identifier is: TEST-DOC-{org_result['organization']['id'][:8]}
    
    We provide the following services:
    - Document digitization
    - Secure storage solutions
    - Document retrieval systems
    - Document workflow automation
    - Records management
    
    Contact us at info@testdoccorp.example.com or call 555-TEST-DOC.
    """
    
    try:
        response = requests.post(
            f"{BASE_URL}/chatbot/upload_document", 
            headers={"X-API-Key": api_key},
            data={"text": unique_text}
        )
        response.raise_for_status()
        upload_result = response.json()
        
        print(f"Document upload result: {upload_result['status']}")
        if "documents_added" in upload_result:
            print(f"Documents added: {upload_result['documents_added']}")
        print()
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        sys.exit(1)
    
    # Step 4: Check updated usage statistics
    print("Step 4: Checking updated usage statistics...")
    try:
        response = requests.get(
            f"{BASE_URL}/organization/usage",
            headers={"X-API-Key": api_key}
        )
        response.raise_for_status()
        usage_after = response.json()
        
        print(f"Updated vector count: {usage_after['usage']['vector_embeddings']}")
        print(f"Updated storage used: {usage_after['usage']['storage_used']} bytes")
        print(f"Change in vector count: {usage_after['usage']['vector_embeddings'] - usage_before['usage']['vector_embeddings']}")
        print()
    except Exception as e:
        print(f"Error checking usage: {str(e)}")
        sys.exit(1)
    
    # Step 5: Retrieve document content by asking a specific question
    print("Step 5: Retrieving document content...")
    
    # Ask a question that should be answered from the unique document
    unique_id = f"TEST-DOC-{org_result['organization']['id'][:8]}"
    question = f"What is our unique identifier?"
    
    try:
        response = requests.post(
            f"{BASE_URL}/chatbot/ask",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "question": question,
                "session_id": "test_session_doc",
                "mode": "faq",
                "user_data": {"name": "Test User", "email": "test@example.com"}
            }
        )
        response.raise_for_status()
        ask_result = response.json()
        
        print(f"Question: {question}")
        print(f"Answer: {ask_result['answer']}")
        
        # Verify the answer contains the unique identifier
        if unique_id in ask_result['answer']:
            print(f"\n✅ Success: The unique identifier '{unique_id}' was found in the answer!")
        else:
            print(f"\n❌ Failure: The unique identifier '{unique_id}' was NOT found in the answer!")
    except Exception as e:
        print(f"Error asking question: {str(e)}")
        sys.exit(1)
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_document_upload_and_retrieval() 