"""
Test script to verify embeddings and Pinecone vectors
Run this to diagnose the embedding mismatch issue
"""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings

# Initialize
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX", "bayai")
index = pc.Index(index_name)

# Initialize LangChain embeddings (same as engine.py)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1024)

# Test query
test_query = "Do you know carter injury law?"
namespace = "kb_f8d45d4e-9578-4dd1-baba-8e146715accd"

print("\n" + "="*60)
print("EMBEDDINGS TEST")
print("="*60)

# Generate query embedding with LangChain
print(f"\nTest Query: '{test_query}'")
print(f"Namespace: {namespace}")

query_embedding = embeddings.embed_query(test_query)
print(f"\nQuery Embedding (LangChain):")
print(f"  - Type: {type(query_embedding)}")
print(f"  - Length: {len(query_embedding)}")
print(f"  - First 5 values: {query_embedding[:5]}")
print(f"  - Sum: {sum(query_embedding):.6f}")

# Query Pinecone directly
print(f"\n{'='*60}")
print("PINECONE DIRECT QUERY")
print("="*60)

results = index.query(
    vector=query_embedding,
    top_k=5,
    namespace=namespace,
    include_metadata=True,
    include_values=False
)

print(f"\nResults: {len(results.matches)} matches")

if results.matches:
    print("\nTop Matches:")
    for i, match in enumerate(results.matches):
        print(f"\n[Match {i+1}]")
        print(f"  - ID: {match.id}")
        print(f"  - Score: {match.score:.6f}")
        print(f"  - Metadata: {match.metadata}")
else:
    print("\n❌ NO MATCHES FOUND!")
    print("\nThis confirms embedding mismatch.")
    print("The vectors in Pinecone were created with different embeddings.")
    
# Fetch a sample vector to compare
print(f"\n{'='*60}")
print("SAMPLE VECTOR INSPECTION")
print("="*60)

# Get vector IDs
stats = index.describe_index_stats()
if namespace in stats['namespaces']:
    print(f"\nNamespace has {stats['namespaces'][namespace]['vector_count']} vectors")
    
    # Fetch one vector by ID pattern
    fetch_result = index.fetch(
        ids=[f"kb_f8d45d4e-9578-4dd1-baba-8e146715accd_company_overview_0"],
        namespace=namespace
    )
    
    if fetch_result.vectors:
        for vec_id, vec_data in fetch_result.vectors.items():
            print(f"\nVector ID: {vec_id}")
            print(f"  - Dimension: {len(vec_data.values)}")
            print(f"  - First 5 values: {vec_data.values[:5]}")
            print(f"  - Sum: {sum(vec_data.values):.6f}")
            print(f"  - Metadata: {vec_data.metadata}")
            
            # Compare with query embedding
            print(f"\n📊 Comparison:")
            print(f"  - Query sum: {sum(query_embedding):.6f}")
            print(f"  - Vector sum: {sum(vec_data.values):.6f}")
            print(f"  - Difference: {abs(sum(query_embedding) - sum(vec_data.values)):.6f}")
    else:
        print("Could not fetch sample vector")

print(f"\n{'='*60}")
print("CONCLUSION")
print("="*60)
print("""
If no matches are found, it means:
1. The 38 vectors in Pinecone were uploaded with OLD embeddings
2. The query is using NEW LangChain embeddings
3. Even though both use same model/dimensions, they're incompatible

SOLUTION: Use the /api/knowledge-base/rebuild endpoint to:
- Delete all vectors
- Re-upload with correct LangChain embeddings
""")
