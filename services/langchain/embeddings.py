# from langchain_openai import OpenAIEmbeddings
# from dotenv import load_dotenv
# import os
# import numpy as np

# # Load environment variables
# load_dotenv()

# class DimensionReducedEmbeddings:
#     """Wrapper for OpenAI embeddings that reduces dimensions to match Pinecone index"""
    
#     def __init__(self, base_embeddings, target_dim=1024):
#         self.base_embeddings = base_embeddings
#         self.target_dim = target_dim
#         print(f"Initialized DimensionReducedEmbeddings with target dimension: {target_dim}")
    
#     def _reduce_dimensions(self, embeddings):
#         """Reduce dimensions of embeddings to match the target dimension"""
#         if len(embeddings) == 0:
#             return []
        
#         # Simple strategy: truncate to the target dimension
#         reduced = [emb[:self.target_dim] for emb in embeddings]
        
#         # Normalize the vectors to unit length
#         normalized = []
#         for emb in reduced:
#             norm = np.linalg.norm(emb)
#             if norm > 0:
#                 normalized.append([float(x / norm) for x in emb])
#             else:
#                 normalized.append(emb)
        
#         print(f"Reduced embeddings from dimension {len(embeddings[0])} to {len(normalized[0])}")
#         return normalized
    
#     def embed_documents(self, texts):
#         """Embed documents and reduce dimensions"""
#         embeddings = self.base_embeddings.embed_documents(texts)
        
#         # Check if we need to reduce dimensions
#         if len(embeddings) > 0 and len(embeddings[0]) > self.target_dim:
#             print(f"Reducing embeddings dimensions from {len(embeddings[0])} to {self.target_dim}")
#             return self._reduce_dimensions(embeddings)
#         return embeddings
    
#     def embed_query(self, text):
#         """Embed query and reduce dimensions"""
#         embedding = self.base_embeddings.embed_query(text)
        
#         # Check if we need to reduce dimensions
#         if len(embedding) > self.target_dim:
#             print(f"Reducing query embedding dimension from {len(embedding)} to {self.target_dim}")
#             # Truncate and normalize
#             reduced = embedding[:self.target_dim]
#             norm = np.linalg.norm(reduced)
#             if norm > 0:
#                 normalized = [float(x / norm) for x in reduced]
#                 return normalized
#         return embedding

# def initialize_embeddings():
#     """Initialize embeddings with dimension reduction to match Pinecone index"""
#     print("Initializing embeddings with dimension reduction...")
    
#     # Get target dimension from environment or use default
#     target_dim = int(os.getenv("PINECONE_DIMENSION", "1024"))
#     print(f"Using target dimension: {target_dim}")
    
#     # Use OpenAI embeddings
#     base_embeddings = OpenAIEmbeddings(
#         openai_api_key=os.getenv("OPENAI_API_KEY"),
#         openai_api_base="https://api.openai.com/v1",
#         model="text-embedding-3-small"  # This model produces 1536-dimensional embeddings
#     )
    
#     # Create dimension-reduced embeddings to match Pinecone index
#     return DimensionReducedEmbeddings(base_embeddings, target_dim=target_dim) 



from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def initialize_embeddings():
    """Initialize OpenAI embeddings with 1024 dimensions to match Pinecone index"""
    print("Initializing OpenAI embeddings...")
    
    # Use OpenAI text-embedding-3-small with 1024 dimensions (matches Pinecone index)
    embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model="text-embedding-3-small",
        dimensions=1024,  # CRITICAL: Force 1024 dims to match Pinecone index
        openai_api_base="https://api.openai.com/v1"
    )
    
    print("✅ OpenAI embeddings initialized with 1024 dimensions (text-embedding-3-small)")
    return embeddings 