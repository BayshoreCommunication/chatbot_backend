import os
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# Print all environment variables for debugging
print("All environment variables:")
for key, value in os.environ.items():
    if key in ["PINECONE_API_KEY", "PINECONE_ENV", "PINECONE_INDEX"]:
        print(f"{key}: {value}")

# Initialize Pinecone
api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX")

print(f"API Key (truncated): {api_key[:10]}...")
print(f"Index name: {index_name}")

pc = Pinecone(api_key=api_key)

# List all indexes
print("Available indexes:")
indexes = pc.list_indexes()
existing_index_names = [index.name for index in indexes.indexes]
print(existing_index_names)

# Try to connect to the specific index
try:
    index = pc.Index(index_name)
    print(f"Successfully connected to index: {index_name}")
    # Try a simple operation
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")
except Exception as e:
    print(f"Error connecting to index: {str(e)}") 