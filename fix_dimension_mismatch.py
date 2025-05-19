from services.langchain.engine import initialize
from services.langchain.embeddings import initialize_embeddings
from services.langchain.vectorstore import initialize_vectorstore
import os
from dotenv import load_dotenv

# Set the Pinecone dimension to match the existing index
os.environ["PINECONE_DIMENSION"] = "1024"

def fix_dimension_mismatch():
    """Fix the dimension mismatch issue between embeddings and Pinecone"""
    print("Fixing dimension mismatch issue...")
    
    # Re-initialize embeddings with correct dimension
    embeddings = initialize_embeddings()
    print(f"Embeddings initialized with dimension: {os.getenv('PINECONE_DIMENSION')}")
    
    # Re-initialize vectorstore with correct dimension
    pc, index_name, vectorstore, namespace = initialize_vectorstore(embeddings)
    if vectorstore:
        print(f"Successfully re-initialized vectorstore with index: {index_name}")
        # Test a query to verify it works
        try:
            results = vectorstore.similarity_search("test", k=1)
            print(f"Test query found {len(results)} documents - vectorstore is working")
        except Exception as e:
            print(f"Error during test query: {str(e)}")
    else:
        print("Failed to re-initialize vectorstore")
    
    # Re-initialize the entire engine
    initialize()
    print("Engine re-initialized with correct dimension")
    
    print("Dimension mismatch fix completed")

if __name__ == "__main__":
    load_dotenv()
    fix_dimension_mismatch() 