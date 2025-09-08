from typing import Optional, Dict, Any, List
from services.pinecone.faq_vectors import search_faq_embeddings
from services.database import db
from bson import ObjectId

# Initialize collections
faq_collection = db.faqs

def find_matching_faq(
    query: str,
    org_id: str,
    namespace: str = "",
    similarity_threshold: float = 0.80
) -> Optional[Dict[str, Any]]:
    """
    Find the best matching FAQ for a given query using LangChain trained data (vector search only).
    Returns the full FAQ document if a good match is found, otherwise None.
    """
    try:
        # DISABLED: Hardcoded responses - use only LangChain trained data
        # from hardcoded_faq_responses import get_hardcoded_response
        # hardcoded_response = get_hardcoded_response(query)
        
        # if hardcoded_response:
        #     # Return a formatted FAQ response
        #     return {
        #         "id": "hardcoded_faq",
        #         "question": query,
        #         "response": hardcoded_response["answer"],
        #         "category": hardcoded_response["category"],
        #         "similarity_score": 1.0,
        #         "source": "hardcoded"
        #     }
        
        # Use only vector search from LangChain trained data
        similar_faqs = search_faq_embeddings(
            query=query,
            org_id=org_id,
            namespace=namespace,
            top_k=3  # Get top 3 matches to find the best one
        )

        if not similar_faqs:
            return None

        # Get the best match
        best_match = similar_faqs[0]
        
        # Only proceed if the similarity score is above threshold
        if best_match['score'] < similarity_threshold:
            return None

        # Get the full FAQ document from MongoDB
        faq = faq_collection.find_one({
            "_id": ObjectId(best_match['faq_id']),
            "org_id": org_id,
            "is_active": True  # Only return active FAQs
        })

        if not faq:
            return None

        # Format the response
        faq['id'] = str(faq.pop('_id'))
        faq['similarity_score'] = best_match['score']
        
        return faq

    except Exception as e:
        print(f"Error finding matching FAQ: {str(e)}")
        return None

def get_suggested_faqs(
    org_id: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Get a list of suggested FAQs to show to the user"""
    try:
        # Get active FAQs that are marked for persistent menu
        suggested = []
        cursor = faq_collection.find({
            "org_id": org_id,
            "is_active": True,
            "persistent_menu": True
        }).limit(limit)

        for faq in cursor:
            faq['id'] = str(faq.pop('_id'))
            suggested.append(faq)

        return suggested

    except Exception as e:
        print(f"Error getting suggested FAQs: {str(e)}")
        return [] 