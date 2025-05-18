import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
import numpy as np

# Load environment variables
load_dotenv()

# Initialize OpenAI embeddings
openai_api_key = os.getenv("OPENAI_API_KEY")
print(f"OpenAI API Key (truncated): {openai_api_key[:10]}...")

# Initialize Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX")

print(f"Pinecone API Key (truncated): {pinecone_api_key[:10]}...")
print(f"Index name: {index_name}")

# Create a simple document
text = """This is a test document to check if document upload to Pinecone works correctly.
It should be embedded and stored in the vector database.
If you can find this text later through a similarity search, it means everything works!"""

try:
    # Create the embeddings
    embeddings_model = OpenAIEmbeddings(
        openai_api_key=openai_api_key,
        openai_api_base="https://api.openai.com/v1"
    )
    
    # Get the embedding directly
    full_vector = embeddings_model.embed_query(text)
    print("Successfully created embedding")
    print(f"Original vector dimension: {len(full_vector)}")
    
    # Reduce dimensions to match Pinecone index
    reduced_vector = full_vector[:1024]
    
    # Convert to Python list of floats explicitly
    reduced_vector = [float(x) for x in reduced_vector]
    
    # Normalize the vector
    norm = np.linalg.norm(reduced_vector)
    if norm > 0:
        reduced_vector = [float(x / norm) for x in reduced_vector]
    
    print(f"Reduced vector dimension: {len(reduced_vector)}")
    print(f"Vector type: {type(reduced_vector[0])}")
    
    # Initialize Pinecone client
    pc = Pinecone(api_key=pinecone_api_key)
    
    # Print available indexes
    indexes = pc.list_indexes()
    existing_index_names = [index.name for index in indexes.indexes]
    print(f"Available indexes: {existing_index_names}")
    
    # Connect to the specified index
    index = pc.Index(index_name)
    print(f"Successfully connected to index: {index_name}")
    
    # Upsert the vector directly
    index.upsert(
        vectors=[
            {
                "id": "test-document-1",
                "values": reduced_vector,
                "metadata": {"text": text}
            }
        ],
        namespace="test"
    )
    
    print("Successfully upserted vector to Pinecone!")
    
    # Test query
    query_response = index.query(
        namespace="test",
        vector=reduced_vector,
        top_k=1,
        include_metadata=True
    )
    
    print("\nQuery results:")
    print(query_response)
    
except Exception as e:
    print(f"Error: {str(e)}") 