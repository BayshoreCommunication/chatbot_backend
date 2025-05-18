import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Pinecone API key and environment
api_key = os.getenv("PINECONE_API_KEY")
environment = os.getenv("PINECONE_ENV")
index_name = os.getenv("PINECONE_INDEX")

print(f"API Key: {'*' * len(api_key) if api_key else 'Not set'}")
print(f"Environment: {environment}")
print(f"Index Name: {index_name}")

try:
    # Initialize Pinecone
    pc = Pinecone(api_key=api_key)
    print("Pinecone initialized successfully!")
    
    # List indexes
    indexes = pc.list_indexes()
    print("Available indexes:", indexes)
    
    # Create index if it doesn't exist
    if index_name not in [index.name for index in indexes.indexes]:
        print(f"Creating index '{index_name}'...")
        pc.create_index(
            name=index_name,
            dimension=1536,  # OpenAI embeddings dimension
            metric="cosine"
        )
        print(f"Index '{index_name}' created!")
    else:
        print(f"Index '{index_name}' already exists.")
    
    # Connect to the index
    index = pc.Index(index_name)
    print("Connected to index successfully!")
    
except Exception as e:
    print(f"Error: {e}") 