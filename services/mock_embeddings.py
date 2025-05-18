import numpy as np
from typing import List
import hashlib

class MockEmbeddings:
    """Mock embeddings provider that doesn't require API calls.
    
    This generates deterministic embeddings based on the hash of the text.
    """
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generate a deterministic embedding based on the hash of the text."""
        # Create a hash of the text
        hash_object = hashlib.md5(text.encode())
        hash_hex = hash_object.hexdigest()
        
        # Use the hash to seed the random number generator
        seed = int(hash_hex, 16) % (2**32 - 1)
        np.random.seed(seed)
        
        # Generate a random vector
        vector = np.random.normal(0, 1, self.dimension)
        
        # Normalize to unit length
        vector = vector / np.linalg.norm(vector)
        
        return vector.tolist()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of documents."""
        return [self._get_embedding(text) for text in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a query."""
        return self._get_embedding(text) 