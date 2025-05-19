import uuid
from services.database import create_organization, get_organization_by_api_key
from services.langchain.embeddings import initialize_embeddings
from services.langchain.engine import get_org_vectorstore
import os
from dotenv import load_dotenv

# Set the correct dimension for Pinecone
os.environ["PINECONE_DIMENSION"] = "1024"

def test_organization_vectors():
    """Test the organization-specific vector store directly"""
    print("Testing organization vector store directly...")
    
    # 1. Create a test organization
    org_name = f"Test Org {uuid.uuid4().hex[:6]}"
    org = create_organization(name=org_name, subscription_tier="standard")
    
    print(f"Created organization: {org['name']}")
    print(f"API Key: {org['api_key']}")
    print(f"Namespace: {org['pinecone_namespace']}")
    
    # 2. Initialize the embeddings
    embeddings = initialize_embeddings()
    print(f"Embeddings initialized with dimension: {os.getenv('PINECONE_DIMENSION')}")
    
    # 3. Get the organization vector store
    org_vectorstore = get_org_vectorstore(org['api_key'])
    if not org_vectorstore:
        print("ERROR: Failed to get organization vector store")
        return
    
    print(f"Successfully got organization vector store with namespace: {org['pinecone_namespace']}")
    
    # 4. Add a test document with a unique identifier
    test_content = f"""
    This is a test document for {org_name}.
    
    IDENTIFIER: ORG-TEST-{uuid.uuid4().hex[:8]}
    
    This test is running in namespace: {org['pinecone_namespace']}
    """
    
    # Extract identifier
    import re
    matches = re.findall(r'ORG-TEST-[a-zA-Z0-9]+', test_content)
    unique_id = matches[0] if matches else "unknown"
    print(f"Test document unique identifier: {unique_id}")
    
    print("\nAdding document to organization vector store...")
    try:
        doc_id = f"orgtest_{uuid.uuid4().hex[:8]}"
        org_vectorstore.add_texts(
            texts=[test_content],
            ids=[doc_id],
            metadatas=[{"org_test": True, "org_id": org['id']}],
            namespace=org['pinecone_namespace']
        )
        print(f"Successfully added document with ID: {doc_id}")
        
        # Verify it was added
        print("\nTesting retrieval of the added document...")
        
        # Try using the unique identifier
        print(f"Searching for unique ID: {unique_id}")
        results = org_vectorstore.similarity_search(
            unique_id, 
            k=1, 
            namespace=org['pinecone_namespace']
        )
        
        if results and len(results) > 0:
            print("SUCCESS: Found document with unique ID search!")
            print(f"Result content: {results[0].page_content[:100]}...")
        else:
            print("WARNING: Unique ID search returned no results.")
        
        # Try with namespace passed explicitly to similarity_search
        print("\nTrying again with explicit namespace parameter...")
        results = org_vectorstore.similarity_search(
            unique_id, 
            k=1, 
            namespace=org['pinecone_namespace']
        )
        
        if results and len(results) > 0:
            print("SUCCESS: Found document with explicit namespace parameter!")
            print(f"Result content: {results[0].page_content[:100]}...")
        else:
            print("WARNING: Explicit namespace search returned no results.")
        
    except Exception as e:
        print(f"Error during vector store operations: {str(e)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    load_dotenv()
    test_organization_vectors() 