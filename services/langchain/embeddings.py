import numpy as np
from langchain.embeddings.base import Embeddings
from langchain_openai import OpenAIEmbeddings
import os

# Define a custom embedding class that reduces vector dimensions
class DimensionReducedEmbeddings(Embeddings):
    def __init__(self, base_embeddings, target_dim=1024):
        self.base_embeddings = base_embeddings
        self.target_dim = target_dim
        
    def embed_documents(self, texts):
        # Get the original embeddings
        original_embeddings = self.base_embeddings.embed_documents(texts)
        # Reduce dimensions and convert to Python float
        reduced_embeddings = []
        for emb in original_embeddings:
            # Convert to Python list of floats
            reduced_emb = [float(x) for x in emb[:self.target_dim]]
            # Normalize
            reduced_embeddings.append(self._normalize(reduced_emb))
        return reduced_embeddings
    
    def embed_query(self, text):
        # Get the original embedding
        original_embedding = self.base_embeddings.embed_query(text)
        # Reduce dimensions and convert to Python floats
        reduced_embedding = [float(x) for x in original_embedding[:self.target_dim]]
        # Normalize the embedding after reduction
        return self._normalize(reduced_embedding)
    
    def _normalize(self, v):
        # Normalize the vector to have unit length
        norm = np.linalg.norm(v)
        if norm > 0:
            return [float(x / norm) for x in v]
        return [float(x) for x in v]

def initialize_embeddings():
    # Use actual OpenAI embeddings
    base_embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base="https://api.openai.com/v1"
    )
    
    # Create dimension-reduced embeddings to match Pinecone index
    return DimensionReducedEmbeddings(base_embeddings, target_dim=1024) 