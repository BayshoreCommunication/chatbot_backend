from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import os
import uuid
import numpy as np

# Load environment variables
load_dotenv()

# Custom dimension reducer
class DimensionReducer:
    def __init__(self, embeddings, target_dim=1024):
        self.embeddings = embeddings
        self.target_dim = target_dim
    
    def embed_documents(self, texts):
        original_embeddings = self.embeddings.embed_documents(texts)
        return self._reduce_embeddings(original_embeddings)
    
    def embed_query(self, text):
        original_embedding = self.embeddings.embed_query(text)
        # Reduce dimensions
        reduced = original_embedding[:self.target_dim]
        # Normalize
        norm = np.linalg.norm(reduced)
        if norm > 0:
            return [float(x / norm) for x in reduced]
        return reduced
    
    def _reduce_embeddings(self, embeddings):
        reduced = []
        for emb in embeddings:
            # Truncate to target dimension
            truncated = emb[:self.target_dim]
            # Normalize
            norm = np.linalg.norm(truncated)
            if norm > 0:
                reduced.append([float(x / norm) for x in truncated])
            else:
                reduced.append([float(x) for x in truncated])
        return reduced

def test_direct_vectorstore_access():
    """Directly test Pinecone vector store functionality"""
    print("Testing direct vector store access...\n")
    
    # Get API keys
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
    
    print(f"Pinecone API Key (truncated): {pinecone_api_key[:10]}...")
    print(f"OpenAI API Key (truncated): {openai_api_key[:10]}...")
    print(f"Using index: {index_name}")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=pinecone_api_key)
    
    # Check available indexes
    indexes = pc.list_indexes()
    available_indexes = [index.name for index in indexes.indexes]
    print(f"Available indexes: {available_indexes}")
    
    if index_name not in available_indexes:
        print(f"Index {index_name} not found. Creating it...")
        pc.create_index(
            name=index_name,
            dimension=1024,  # Match the dimension of the existing index
            metric="cosine"
        )
    
    # Create a test namespace
    test_namespace = f"test_ns_{uuid.uuid4().hex[:8]}"
    print(f"Using test namespace: {test_namespace}")
    
    # Initialize embeddings with dimension reduction
    base_embeddings = OpenAIEmbeddings(
        openai_api_key=openai_api_key,
        model="text-embedding-3-small"
    )
    embeddings = DimensionReducer(base_embeddings, target_dim=1024)
    
    # Initialize vector store
    index = pc.Index(index_name)
    vectorstore = PineconeVectorStore(
        index=index,
        embedding=embeddings,
        text_key="text",
        namespace=test_namespace
    )
    
    # Test document with a unique identifier
    test_doc = f"""
    This is a test document for direct vector store testing.
    
    Our unique identifier is: DIRECT-TEST-{uuid.uuid4().hex[:8]}
    
    This document is stored in namespace: {test_namespace}
    """
    
    unique_id = None
    import re
    matches = re.findall(r'DIRECT-TEST-[a-zA-Z0-9]+', test_doc)
    if matches:
        unique_id = matches[0]
        print(f"Found unique ID in document: {unique_id}")
    
    # Add document to vector store
    print("\nAdding document to vector store...")
    try:
        doc_id = f"test_doc_{uuid.uuid4().hex[:8]}"
        vectorstore.add_texts(
            texts=[test_doc],
            ids=[doc_id],
            metadatas=[{"test": True}],
            namespace=test_namespace
        )
        print(f"Successfully added document with ID: {doc_id}")
        
        # Get stats
        stats = index.describe_index_stats()
        total_vectors = stats.total_vector_count
        ns_stats = stats.namespaces.get(test_namespace, {})
        ns_vectors = ns_stats.vector_count if hasattr(ns_stats, 'vector_count') else 0
        
        print(f"Total vectors: {total_vectors}")
        print(f"Vectors in namespace {test_namespace}: {ns_vectors}")
        
        # Verify with similarity search
        print("\nTesting retrieval...")
        
        # First, try using the unique ID
        if unique_id:
            print(f"Searching for unique ID: {unique_id}")
            results = vectorstore.similarity_search(unique_id, k=1, namespace=test_namespace)
            if results and len(results) > 0:
                print("SUCCESS: Found document with unique ID search!")
                print(f"Result content: {results[0].page_content[:100]}...")
            else:
                print("WARNING: Unique ID search returned no results.")
        
        # Next, try a more general search
        print("\nSearching for general term 'test document'...")
        results = vectorstore.similarity_search("test document", k=1, namespace=test_namespace)
        if results and len(results) > 0:
            print("SUCCESS: Found document with general search!")
            print(f"Result content: {results[0].page_content[:100]}...")
        else:
            print("WARNING: General search returned no results.")
        
        # Clean up the test namespace
        print("\nCleaning up test namespace...")
        index.delete(delete_all=True, namespace=test_namespace)
        print(f"Deleted all vectors in namespace: {test_namespace}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    test_direct_vectorstore_access() 