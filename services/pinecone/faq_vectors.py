from typing import List, Dict, Any
from pinecone import Pinecone
from services.openai_service import get_embeddings
from services.database import db
import os
from bson import ObjectId

# Initialize FAQ vectors collection for metadata
faq_vectors = db.faq_vectors

# Global Pineconeclient
pc = None

def init_pinecone():
    """Initialize Pinecone with environment credentials"""
    global pc
    pc = Pinecone(
        api_key=os.getenv("PINECONE_API_KEY"),
        environment=os.getenv("PINECONE_ENV")
    )

def get_faq_index():
    """Get or create the FAQ index in Pinecone"""
    global pc
    if not pc:
        init_pinecone()

    INDEX_NAME = os.getenv("PINECONE_INDEX", "bayai")
    DIMENSION = 1024  # Match your existing index dimension

    # Get existing index
    try:
        return pc.Index(INDEX_NAME)
    except Exception as e:
        print(f"Error getting index: {str(e)}")
        return None

async def upsert_faq_embedding(
    faq_id: str,
    question: str,
    org_id: str,
    namespace: str
):
    """Create or update FAQ embedding in Pinecone"""
    try:
        if not namespace:
            print(f"No namespace provided for organization {org_id}")
            return False

        # Get embeddings for the question
        embeddings = get_embeddings(question)
        if not embeddings:
            print(f"Failed to generate embeddings for FAQ {faq_id}")
            return False

        # Truncate embeddings to match index dimension
        embeddings = embeddings[:1024]

        # Get Pinecone index
        index = get_faq_index()
        if not index:
            return False

        # Prepare vector data
        vector_data = {
            'id': f"faq_{faq_id}",
            'values': embeddings,
            'metadata': {
                'faq_id': faq_id,
                'org_id': org_id,
                'question': question
            }
        }

        # Upsert to Pinecone with organization namespace
        index.upsert(
            vectors=[vector_data],
            namespace=namespace
        )

        # Store reference in MongoDB
        faq_vectors.update_one(
            {'faq_id': faq_id},
            {
                '$set': {
                    'faq_id': faq_id,
                    'org_id': org_id,
                    'vector_id': f"faq_{faq_id}",
                    'namespace': namespace
                }
            },
            upsert=True
        )

        return True
    except Exception as e:
        print(f"Error upserting FAQ embedding: {str(e)}")
        return False

async def delete_faq_embedding(faq_id: str, namespace: str):
    """Delete FAQ embedding from Pinecone"""
    try:
        if not namespace:
            print(f"No namespace provided for FAQ {faq_id}")
            return False

        # Get Pinecone index
        index = get_faq_index()
        if not index:
            return False

        # Delete vector from organization namespace
        index.delete(
            ids=[f"faq_{faq_id}"],
            namespace=namespace
        )

        # Remove reference from MongoDB
        faq_vectors.delete_one({'faq_id': faq_id})

        return True
    except Exception as e:
        print(f"Error deleting FAQ embedding: {str(e)}")
        return False

def search_faq_embeddings(
    query: str,
    org_id: str,
    namespace: str,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """Search for similar FAQs using vector similarity"""
    try:
        if not namespace:
            print(f"No namespace provided for organization {org_id}")
            return []

        # Get embeddings for the query
        query_embedding = get_embeddings(query)
        if not query_embedding:
            return []

        # Truncate embeddings to match index dimension
        query_embedding = query_embedding[:1024]

        # Get Pinecone index
        index = get_faq_index()
        if not index:
            return []

        # Search in Pinecone using organization namespace
        search_results = index.query(
            vector=query_embedding,
            namespace=namespace,
            filter={'org_id': org_id},
            top_k=top_k,
            include_metadata=True
        )

        # Extract FAQ IDs and scores
        results = []
        for match in search_results.matches:
            results.append({
                'faq_id': match.metadata['faq_id'],
                'score': match.score,
                'question': match.metadata['question']
            })

        return results
    except Exception as e:
        print(f"Error searching FAQ embeddings: {str(e)}")
        return [] 