"""
Script to fix embedding mismatch by deleting old vectors and re-uploading
Run this once to regenerate all vectors with correct embeddings
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
from services.database import db
import asyncio

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX", "bayai")
index = pc.Index(index_name)

async def fix_knowledge_base(user_id: str, org_id: str):
    """Delete vectors and trigger re-upload for a specific knowledge base"""
    
    # Get knowledge base
    kb = db.knowledge_bases.find_one({"userId": user_id})
    if not kb:
        print(f"❌ No knowledge base found for user_id: {user_id}")
        return
    
    vectorstore_id = kb.get("vectorStoreId")
    company_name = kb.get("companyName")
    
    print(f"\n{'='*60}")
    print(f"🔧 Fixing embeddings for: {company_name}")
    print(f"   User ID: {user_id}")
    print(f"   Org ID: {org_id}")
    print(f"   Namespace: {vectorstore_id}")
    print(f"{'='*60}\n")
    
    if not vectorstore_id:
        print("❌ No vectorStoreId found in knowledge base")
        return
    
    # Delete all vectors in the namespace
    print(f"🗑️  Deleting all vectors in namespace: {vectorstore_id}")
    try:
        index.delete(delete_all=True, namespace=vectorstore_id)
        print(f"✅ Successfully deleted vectors from namespace: {vectorstore_id}")
    except Exception as e:
        print(f"⚠️  Error deleting vectors: {e}")
    
    # Re-upload with correct embeddings
    print(f"\n📤 Re-uploading knowledge base with correct embeddings...")
    from services.langchain.knowledge_base import build_knowledge_base_auto
    
    website = None
    sources = kb.get("sources", [])
    if sources:
        for source in sources:
            if source.get("type") == "website" and source.get("url"):
                website = source["url"]
                break
    
    try:
        result = await build_knowledge_base_auto(
            user_id=user_id,
            organization_id=org_id,
            company_name=company_name,
            website=website
        )
        print(f"✅ Knowledge base re-uploaded successfully!")
        print(f"   New vectorStoreId: {result.get('vectorStoreId')}")
        print(f"   Total chunks: {len(result.get('aiChunks', []))}")
    except Exception as e:
        print(f"❌ Error re-uploading: {e}")
        import traceback
        traceback.print_exc()

async def fix_all_knowledge_bases():
    """Fix all knowledge bases in the database"""
    
    print("\n" + "="*60)
    print("🚀 FIXING ALL KNOWLEDGE BASES")
    print("="*60 + "\n")
    
    # Get all knowledge bases
    kbs = list(db.knowledge_bases.find({}))
    print(f"Found {len(kbs)} knowledge bases\n")
    
    for kb in kbs:
        user_id = kb.get("userId")
        org_id = kb.get("organizationId")
        
        if user_id and org_id:
            await fix_knowledge_base(user_id, org_id)
            print("\n" + "-"*60 + "\n")
        else:
            print(f"⚠️  Skipping KB with missing IDs: {kb.get('_id')}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 2:
        # Fix specific knowledge base
        user_id = sys.argv[1]
        org_id = sys.argv[2]
        asyncio.run(fix_knowledge_base(user_id, org_id))
    else:
        # Fix all knowledge bases
        print("\n⚠️  This will re-upload ALL knowledge bases with correct embeddings.")
        print("   This may take several minutes and consume API credits.")
        confirm = input("\nContinue? (yes/no): ")
        
        if confirm.lower() == "yes":
            asyncio.run(fix_all_knowledge_bases())
            print("\n✅ All knowledge bases fixed!")
        else:
            print("❌ Cancelled")
