from pinecone import Pinecone
from typing import List, Dict, Any
from .llm import embeddings
from .config import PINECONE_API_KEY, PINECONE_INDEX, RAG_TOP_K, RAG_SIMILARITY_THRESHOLD

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

def search_kb(query: str, namespace: str, top_k: int = RAG_TOP_K, threshold: float = RAG_SIMILARITY_THRESHOLD) -> str:
    """
    Search knowledge base using semantic search.
    
    Args:
        query: User question to search for
        namespace: Organization-specific namespace (vectorStoreId)
        top_k: Number of results to retrieve
        threshold: Minimum similarity score threshold
        
    Returns:
        Formatted string of relevant context from knowledge base
    """
    try:
        print(f"\n[RAG SEARCH] Query: {query}")
        print(f"[RAG SEARCH] Namespace: {namespace}")
        
        # Generate embedding for the query
        vector = embeddings.embed_query(query)

        # Search Pinecone
        results = index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        print(f"[RAG SEARCH] Found {len(results.matches)} total matches")

        # Filter and format results
        docs = []
        for idx, match in enumerate(results.matches):
            score = match.score
            print(f"[RAG SEARCH]   Match {idx+1}: score={score:.4f}, title={match.metadata.get('title', 'N/A')[:50]}")
            
            if score >= threshold:
                content = match.metadata.get("content", "").strip()
                source = match.metadata.get("title", "Knowledge Base")
                
                if content and len(content) > 10:
                    formatted_doc = f"Source: {source}\n{content}"
                    docs.append(formatted_doc)
                    print(f"[RAG SEARCH] ✓ Added document from {source}")
            else:
                print(f"[RAG SEARCH] ⏭️ Skipping (score {score:.4f} < threshold {threshold})")

        if docs:
            result = "\n\n---\n\n".join(docs)
            print(f"[RAG SEARCH] ✅ Returning {len(docs)} relevant documents")
            return result
        else:
            print(f"[RAG SEARCH] ❌ No relevant documents found")
            return ""
            
    except Exception as e:
        print(f"[RAG SEARCH] ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ""

def get_relevant_sources(query: str, namespace: str, top_k: int = RAG_TOP_K, threshold: float = RAG_SIMILARITY_THRESHOLD) -> List[Dict[str, Any]]:
    """
    Get relevant sources with metadata for citation purposes.
    
    Returns:
        List of dictionaries containing source information
    """
    try:
        vector = embeddings.embed_query(query)
        
        results = index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        sources = []
        for match in results.matches:
            if match.score >= threshold:
                sources.append({
                    "title": match.metadata.get("title", "Unknown Source"),
                    "score": float(match.score),
                    "url": match.metadata.get("url", ""),
                    "content_preview": match.metadata.get("content", "")[:200]
                })
        
        return sources
        
    except Exception as e:
        print(f"[RAG] Error getting sources: {e}")
        return []
