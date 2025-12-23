from pinecone import Pinecone
from openai import OpenAI
import os

pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index('bayai')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

namespace = 'kb_f8d45d4e-9578-4dd1-baba-8e146715accd'

print("Testing searches in namespace:", namespace)
print("="*80)

# Test 1: "services"
print("\nTest 1: Searching for 'services'")
emb = client.embeddings.create(input='services', model='text-embedding-3-small', dimensions=1024)
results = index.query(vector=emb.data[0].embedding, top_k=5, namespace=namespace, include_metadata=True)
print(f'Found {len(results.matches)} results:')
for m in results.matches:
    print(f'  Score: {m.score:.4f}')
    print(f'  Title: {m.metadata.get("title", "N/A")}')
    print(f'  Content: {m.metadata.get("content", "N/A")[:150]}...\n')

# Test 2: "what do you do"
print("\nTest 2: Searching for 'what do you do'")
emb = client.embeddings.create(input='what do you do', model='text-embedding-3-small', dimensions=1024)
results = index.query(vector=emb.data[0].embedding, top_k=5, namespace=namespace, include_metadata=True)
print(f'Found {len(results.matches)} results:')
for m in results.matches:
    print(f'  Score: {m.score:.4f}')
    print(f'  Title: {m.metadata.get("title", "N/A")}')
    print(f'  Content: {m.metadata.get("content", "N/A")[:150]}...\n')

# Test 3: The exact query the agent uses
print("\nTest 3: Searching for 'services offered company services'")
emb = client.embeddings.create(input='services offered company services', model='text-embedding-3-small', dimensions=1024)
results = index.query(vector=emb.data[0].embedding, top_k=5, namespace=namespace, include_metadata=True)
print(f'Found {len(results.matches)} results:')
for m in results.matches:
    print(f'  Score: {m.score:.4f}')
    print(f'  Title: {m.metadata.get("title", "N/A")}')
    print(f'  Content: {m.metadata.get("content", "N/A")[:150]}...\n')
