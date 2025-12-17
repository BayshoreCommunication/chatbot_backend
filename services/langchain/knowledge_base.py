"""
Knowledge Base Service with OpenAI Web Search Integration
Automatically gathers company information using OpenAI web search tools
Stores in MongoDB and Vector Database (Pinecone)
"""

import os
import logging
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from bson import ObjectId
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# LangChain Imports for Document Processing
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from services.database import db

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize embeddings (MUST match engine.py configuration exactly!)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1024)
logger.info("✅ Embeddings initialized for knowledge base uploads (1024 dimensions)")

# Initialize Pinecone
pinecone_index = None
pc = None
try:
    if os.getenv("PINECONE_API_KEY"):
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        pinecone_index = pc.Index(os.getenv("PINECONE_INDEX", "bayai"))
        logger.info("✅ Pinecone initialized successfully")
    else:
        logger.warning("⚠️ PINECONE_API_KEY not found in environment variables")
except Exception as e:
    logger.warning(f"⚠️ Pinecone not available: {e}")

# MongoDB collection
knowledge_bases = db.knowledge_bases


# ==========================================
# TEXT SPLITTING & PROCESSING
# ==========================================

def get_text_splitter():
    """Get standard text splitter for consistency"""
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )

async def load_and_split_document(
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    text: Optional[str] = None,
    max_pages: int = 1
) -> List[Document]:
    """
    Load and split document from various sources
    """
    documents = []
    
    try:
        if file_path:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
                documents = loader.load()
            else:
                # Text file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                documents = [Document(page_content=content, metadata={"source": file_path})]
                
        elif url:
            if max_pages > 1:
                # Use comprehensive scraping
                documents = scrape_website_content_recursive(url, max_pages)
            else:
                # Single page
                try:
                    loader = WebBaseLoader(url)
                    documents = loader.load()
                except Exception as e:
                    # Fallback to simple scraping
                    logger.warning(f"WebBaseLoader failed for {url}, using fallback: {e}")
                    content = await scrape_website(url)
                    documents = [Document(page_content=content, metadata={"source": url})]

        elif text:
            documents = [Document(page_content=text, metadata={"source": "manual_input"})]

        # Split documents
        text_splitter = get_text_splitter()
        split_docs = text_splitter.split_documents(documents) 
        
        return split_docs
        
    except Exception as e:
        logger.error(f"Error loading/splitting document: {e}")
        return []

def scrape_website_content_recursive(base_url: str, max_pages: int = 10) -> List[Document]:
    """
    Recursive scraping logic (adapted from vectorstore.py)
    """
    logger.info(f"🕷️ Starting recursive scrape of {base_url} (max {max_pages} pages)")
    
    visited_urls = set()
    to_visit = [base_url]
    documents = []
    count = 0
    base_domain = urlparse(base_url).netloc
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    while to_visit and count < max_pages:
        current_url = to_visit.pop(0)
        if current_url in visited_urls:
            continue
            
        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            if response.status_code != 200: continue
            
            visited_urls.add(current_url)
            count += 1
            
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
                
            text = soup.get_text(separator="\n", strip=True)
            text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
            
            if len(text) > 100:
                documents.append(Document(
                    page_content=text, 
                    metadata={"source": current_url, "title": soup.title.string if soup.title else ""}
                ))
            
            # Find links
            if count < max_pages:
                for link in soup.find_all("a", href=True):
                    full_url = urljoin(current_url, link["href"])
                    parsed = urlparse(full_url)
                    
                    if (parsed.netloc == base_domain or not parsed.netloc) and \
                       full_url not in visited_urls and \
                       full_url not in to_visit and \
                       not full_url.lower().endswith((".pdf", ".jpg", ".png")):
                        to_visit.append(full_url)
                        
        except Exception as e:
            logger.error(f"Error scraping {current_url}: {e}")
            
    return documents


# ==========================================
# AUTO-BUILD LOGIC (EXISTING)
# ==========================================

def extract_schema_org(html_content: str) -> Dict[str, Any]:
    """Extract Schema.org structured data (JSON-LD) from HTML"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        schema_data = {}
        
        # Find all JSON-LD scripts
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                # Merge data
                if isinstance(data, dict):
                    schema_data.update(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            schema_data.update(item)
            except json.JSONDecodeError:
                continue
        
        logger.info(f"📋 Extracted Schema.org data: {list(schema_data.keys())}")
        return schema_data
    except Exception as e:
        logger.error(f"Error extracting schema.org: {e}")
        return {}

def find_pdfs_on_website(base_url: str, html_content: str) -> List[str]:
    """Discover PDF links on website"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        pdf_urls = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf'):
                full_url = urljoin(base_url, href)
                pdf_urls.append(full_url)
        
        logger.info(f"📄 Found {len(pdf_urls)} PDFs on website")
        return pdf_urls[:5]  # Limit to 5 PDFs
    except Exception as e:
        logger.error(f"Error finding PDFs: {e}")
        return []

async def scrape_website(url: str) -> str:
    """Scrape website content using BeautifulSoup (Simple)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe']):
            element.decompose()
        content = soup.get_text(separator=' ', strip=True)
        return ' '.join(content.split())[:10000]
    except Exception as e:
        logger.error(f"❌ Error scraping {url}: {e}")
        return ""

async def detect_missing_info(extracted_data: Dict[str, Any], company_name: str) -> Dict[str, Any]:
    """Use GPT-4o to detect gaps and suggest enhancements"""
    try:
        logger.info(f"🔍 Detecting missing information for: {company_name}")
        
        prompt = f"""Analyze this company data and identify CRITICAL missing information for a chatbot:

Company: {company_name}
Current Data: {json.dumps(extracted_data, indent=2)[:3000]}

Identify:
1. Missing contact info (phone, email, address, hours)
2. Missing service/product details
3. Missing pricing information
4. Missing team/about info
5. Common customer questions we CAN'T answer yet

Return JSON with:
{{
  "missing_critical": ["item1", "item2"],
  "missing_important": ["item1", "item2"],
  "confidence_score": 0-100,
  "suggestions": "How to fill gaps"
}}"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a data completeness analyst."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1024,
            temperature=0.2
        )
        
        gaps = json.loads(response.choices[0].message.content or "{}")
        logger.info(f"📊 Completeness: {gaps.get('confidence_score', 0)}%")
        return gaps
        
    except Exception as e:
        logger.error(f"❌ Gap detection failed: {e}")
        return {"confidence_score": 50, "missing_critical": []}

async def extract_structured_data(combined_content: str, company_name: str, website: Optional[str] = None) -> Dict[str, Any]:
    """Extract structured data from raw content using OpenAI"""
    try:
        logger.info(f"🧠 Extracting structured data for {company_name}...")
        enhanced_prompt = """You are an expert at extracting and structuring company information for AI chatbot use.
Extract comprehensive, chatbot-friendly information in this exact JSON format:
{
  "companyOverview": "Detailed 2-3 paragraph overview...",
  "tagline": "Main company tagline",
  "services": [{"name": "Service Name", "description": "Desc..."}],
  "products": [{"name": "Product Name", "description": "Desc..."}],
  "contactInfo": {"phone": "...", "email": "...", "address": "...", "website": "..."},
  "keyFeatures": [{"feature": "...", "description": "..."}],
  "pricing": {"structure": "...", "details": "...", "freeServices": []},
  "faqs": [{"question": "...", "answer": "...", "category": "..."}],
  "team": [{"name": "...", "role": "..."}],
  "testimonials": [{"text": "...", "author": "..."}],
  "processSteps": [{"step": 1, "title": "...", "description": "..."}],
  "chatbotResponses": {"greeting": "...", "callToAction": "..."}
}
Use null for missing fields. Be comprehensive."""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": f"Company: {company_name}\nWebsite: {website or 'N/A'}\n\nInfo:\n{combined_content[:30000]}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096
        )
        import json
        return json.loads(response.choices[0].message.content or "{}")
    except Exception as e:
        logger.error(f"❌ Error extracting structured data: {e}")
        return {"companyOverview": combined_content[:500]}

def create_chatbot_chunks(structured_data: Dict[str, Any], company_name: str) -> List[Dict[str, Any]]:
    """Create AI-friendly chunks optimized for chatbot responses"""
    chunks = []
    
    # Overview
    if structured_data.get("companyOverview"):
        chunks.append({
            "type": "company_overview",
            "title": f"About {company_name}",
            "content": structured_data["companyOverview"],
            "metadata": {"use_for": ["general_inquiry", "company_info", "introduction"]}
        })
    
    # Contact
    contact = structured_data.get("contactInfo", {})
    if contact:
        contact_text = f"Contact {company_name}:\n"
        if contact.get("phone"): contact_text += f"📞 {contact['phone']}\n"
        if contact.get("email"): contact_text += f"📧 {contact['email']}\n"
        if contact.get("address"): contact_text += f"📍 {contact['address']}\n"
        if contact.get("website"): contact_text += f"🌐 {contact['website']}\n"
        if contact.get("availability"): contact_text += f"🕒 {contact['availability']}\n"
        
        chunks.append({
            "type": "contact_info",
            "title": f"Contact {company_name}",
            "content": contact_text.strip(),
            "metadata": {"use_for": ["contact", "phone", "email", "address", "location"]}
        })

    # Services
    services = structured_data.get("services", [])
    if isinstance(services, list):
        for s in services:
            if isinstance(s, dict):
                chunks.append({
                    "type": "service",
                    "title": s.get("name", "Service"),
                    "content": f"{company_name} Service: {s.get('name')}\n\n{s.get('description', '')}",
                    "metadata": {"use_for": ["services", "what_we_do"]}
                })

    # FAQs
    faqs = structured_data.get("faqs", [])
    if isinstance(faqs, list):
        for f in faqs:
            if isinstance(f, dict):
                chunks.append({
                    "type": "faq",
                    "title": f.get("question", "FAQ"),
                    "content": f"Q: {f.get('question')}\n\nA: {f.get('answer')}",
                    "metadata": {"use_for": ["faq", "questions"]}
                })
                
    # Pricing
    pricing = structured_data.get("pricing")
    if pricing:
        content = str(pricing) if not isinstance(pricing, dict) else f"Structure: {pricing.get('structure')}\nDetails: {pricing.get('details')}"
        chunks.append({
            "type": "pricing",
            "title": "Pricing",
            "content": content,
            "metadata": {"use_for": ["pricing", "cost"]}
        })

    return chunks

async def store_chunks_in_vector_db(
    chunks: List[Dict[str, Any]],
    user_id: str,
    organization_id: str,
    company_name: str
) -> str:
    """Store AI chunks in Pinecone"""
    try:
        if not pinecone_index: return None
        
        # Standardized namespace
        namespace = f"kb_{organization_id}"
        logger.info(f"📤 Storing {len(chunks)} chunks in Pinecone (namespace: {namespace})...")
        
        vectors = []
        for i, chunk in enumerate(chunks):
            # Generate embedding using LangChain (same as query)
            emb = embeddings.embed_query(chunk["content"])
            
            # Upsert
            vectors.append({
                "id": f"kb_{organization_id}_{chunk['type']}_{i}",
                "values": emb,
                "metadata": {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "company_name": company_name,
                    "chunk_type": chunk["type"],
                    "title": chunk["title"],
                    "content": chunk["content"][:2000],  # Limit text in metadata
                    "use_for": ",".join(chunk["metadata"].get("use_for", []))
                }
            })
        
        pinecone_index.upsert(vectors=vectors, namespace=namespace)
        return namespace
        
    except Exception as e:
        logger.error(f"❌ Error storing chunks: {e}")
        return None


# ==========================================
# UNIFIED ADD DOCUMENT FUNCTION
# ==========================================

async def add_document_to_knowledge_base(
    user_id: str,
    organization_id: str,
    company_name: str,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    text: Optional[str] = None,
    max_pages: int = 1
) -> Dict[str, Any]:
    """
    Unified function to add any document type to the Knowledge Base.
    Handles Text, URLs, and PDFs.
    """
    try:
        # 1. Load and Split
        split_docs = await load_and_split_document(file_path, url, text, max_pages)
        if not split_docs:
            raise Exception("No content extracted from source")

        logger.info(f"📄 Processed {len(split_docs)} chunks from source")

        # 2. Store in Pinecone
        if not pinecone_index:
            raise Exception("Pinecone not initialized")

        namespace = f"kb_{organization_id}"
        vectors = []
        
        for i, doc in enumerate(split_docs):
            # Generate ID
            doc_hash = str(hash(doc.page_content))
            vector_id = f"doc_{organization_id}_{doc_hash}_{i}"
            
            # Embed using LangChain (same as query)
            emb = embeddings.embed_query(doc.page_content)
            
            # Metadata
            vectors.append({
                "id": vector_id,
                "values": emb,
                "metadata": {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "company_name": company_name,
                    "chunk_type": "document",
                    "title": doc.metadata.get("title", "Document Segment"),
                    "source": doc.metadata.get("source", "unknown"),
                    "content": doc.page_content[:2000],
                    "use_for": "general_knowledge"
                }
            })
            
            # Batch upsert if too large (Pinecone limit is usually 100-1000)
            if len(vectors) >= 100:
                pinecone_index.upsert(vectors=vectors, namespace=namespace)
                vectors = []
        
        # Upsert remaining
        if vectors:
            pinecone_index.upsert(vectors=vectors, namespace=namespace)

        # 3. Update MongoDB Knowledge Base
        kb = knowledge_bases.find_one({"userId": user_id, "organizationId": organization_id})
        
        source_entry = {
            "type": "document" if file_path else "website" if url else "manual",
            "url": url,
            "filePath": file_path,
            "processedAt": datetime.now(),
            "chunkCount": len(split_docs)
        }
        
        if kb:
            knowledge_bases.update_one(
                {"_id": kb["_id"]},
                {
                    "$push": {"sources": source_entry},
                    "$set": {"updatedAt": datetime.now(), "vectorStoreId": namespace}
                }
            )
        else:
            # Create if not exists (minimal)
            knowledge_bases.insert_one({
                "userId": user_id,
                "organizationId": organization_id,
                "companyName": company_name,
                "sources": [source_entry],
                "vectorStoreId": namespace,
                "status": "active",
                "createdAt": datetime.now(),
                "updatedAt": datetime.now()
            })
            
        return {"status": "success", "chunks": len(split_docs), "namespace": namespace}
    
    except Exception as e:
        logger.error(f"❌ Error adding document to KB: {e}")
        raise

async def build_knowledge_base_auto(
    user_id: str,
    organization_id: str,
    company_name: str,
    website: Optional[str] = None
) -> Dict[str, Any]:
    """Enhanced auto-build with multi-page crawling, Schema.org, and PDF extraction"""
    try:
        logger.info(f"🚀 Building enhanced knowledge base for {company_name}")
        
        # 1. MULTI-PAGE CRAWLING (10 pages)
        combined_content = ""
        sources = []
        schema_data = {}
        pdf_urls = []
        docs = []
        
        if website:
            logger.info(f"🕷️ Starting multi-page crawl of {website}")
            
            # Get homepage first for Schema.org and PDFs
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(website, headers=headers, timeout=10)
                html_content = response.text
                
                # Extract Schema.org structured data
                schema_data = extract_schema_org(html_content)
                
                # Find PDFs
                pdf_urls = find_pdfs_on_website(website, html_content)
                
            except Exception as e:
                logger.warning(f"⚠️ Error getting homepage: {e}")
            
            # Recursive crawl (10 pages)
            docs = scrape_website_content_recursive(website, max_pages=10)
            for doc in docs:
                combined_content += doc.page_content + "\n\n"
                sources.append({
                    "type": "website", 
                    "url": doc.metadata.get("source", website),
                    "title": doc.metadata.get("title", ""),
                    "content": doc.page_content[:500]
                })
            
            logger.info(f"✅ Crawled {len(docs)} pages")
            
        # 2. EXTRACT PDFs (if found)
        if pdf_urls:
            logger.info(f"📄 Extracting {len(pdf_urls)} PDFs...")
            for pdf_url in pdf_urls:
                try:
                    pdf_docs = await load_and_split_document(url=pdf_url, max_pages=1)
                    for doc in pdf_docs[:3]:  # Limit chunks per PDF
                        combined_content += doc.page_content + "\n\n"
                        sources.append({
                            "type": "pdf",
                            "url": pdf_url,
                            "content": doc.page_content[:500]
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Error extracting PDF {pdf_url}: {e}")
        
        # 3. ENHANCE WITH SCHEMA.ORG DATA
        if schema_data:
            logger.info(f"📋 Adding Schema.org structured data")
            combined_content += f"\n\nStructured Data: {json.dumps(schema_data, indent=2)}"
            sources.append({
                "type": "schema_org",
                "content": json.dumps(schema_data)
            })
        
        # 4. Extract Structure with GPT-4o
        structured = await extract_structured_data(combined_content, company_name, website)
        
        # 5. MERGE SCHEMA.ORG INTO STRUCTURED DATA
        if schema_data:
            # Enhance contact info
            if "@type" in schema_data and "Local" in schema_data.get("@type", ""):
                if not structured.get("contactInfo"):
                    structured["contactInfo"] = {}
                if schema_data.get("telephone"):
                    structured["contactInfo"]["phone"] = schema_data["telephone"]
                if schema_data.get("email"):
                    structured["contactInfo"]["email"] = schema_data["email"]
                if schema_data.get("address"):
                    addr = schema_data["address"]
                    if isinstance(addr, dict):
                        structured["contactInfo"]["address"] = f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')}, {addr.get('addressRegion', '')} {addr.get('postalCode', '')}"
                if schema_data.get("openingHours"):
                    structured["contactInfo"]["availability"] = schema_data["openingHours"]
        
        # 6. DETECT GAPS & COMPLETENESS SCORE
        gaps = await detect_missing_info(structured, company_name)
        completeness_score = gaps.get("confidence_score", 50)
        
        # 7. Create Chunks
        chunks = create_chatbot_chunks(structured, company_name)
        logger.info(f"📦 Created {len(chunks)} chatbot chunks")
        
        # 8. Store in Vector DB
        namespace = await store_chunks_in_vector_db(chunks, user_id, organization_id, company_name)
        
        # 9. Save/Update MongoDB with enhanced metadata
        kb_data = {
            "userId": user_id,
            "organizationId": organization_id,
            "companyName": company_name,
            "website": website,
            "sources": sources,
            "structuredData": structured,
            "schemaOrgData": schema_data,
            "aiChunks": chunks,
            "vectorStoreId": namespace,
            "status": "active",
            "metadata": {
                "totalSources": len(sources),
                "totalChunks": len(chunks),
                "pdfCount": len(pdf_urls),
                "pagesScraped": len(docs),
                "hasSchemaOrg": len(schema_data) > 0,
                "completenessScore": completeness_score,
                "missingInfo": gaps.get("missing_critical", []),
                "lastUpdated": datetime.now(),
                "model": "gpt-4o",
                "quality": "high" if completeness_score >= 80 else "medium" if completeness_score >= 60 else "low"
            },
            "updatedAt": datetime.now(),
            "createdAt": datetime.now()
        }
        
        logger.info(f"✅ Knowledge base built: {len(sources)} sources, {len(chunks)} chunks, {completeness_score}% complete")
        
        knowledge_bases.update_one(
            {"userId": user_id, "organizationId": organization_id},
            {"$set": kb_data},
            upsert=True
        )
        
        return knowledge_bases.find_one({"userId": user_id, "organizationId": organization_id})

    except Exception as e:
        logger.error(f"❌ Error building KB: {e}")
        raise

async def get_chatbot_chunks_by_intent(user_id: str, organization_id: str, intent: str) -> List[Dict[str, Any]]:
    """Get chunks filtered by intent"""
    kb = knowledge_bases.find_one({"userId": user_id, "organizationId": organization_id})
    if not kb or "aiChunks" not in kb: return []
    
    return [c for c in kb["aiChunks"] if intent.lower() in [u.lower() for u in c.get("metadata", {}).get("use_for", [])]]

async def get_all_chatbot_context(user_id: str, organization_id: str) -> str:
    """Get full context string"""
    kb = knowledge_bases.find_one({"userId": user_id, "organizationId": organization_id})
    if not kb: return "No knowledge base found."
    
    context = f"=== KNOWLEDGE BASE: {kb.get('companyName')} ===\n\n"
    for chunk in kb.get("aiChunks", []):
        context += f"## {chunk.get('title')}\n{chunk.get('content')}\n---\n"
    return context

async def query_vector_db(query: str, organization_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Query Pinecone"""
    if not pinecone_index: return []
    try:
        namespace = f"kb_{organization_id}"
        # Use LangChain embeddings (same as query in engine.py)
        emb = embeddings.embed_query(query)
        
        results = pinecone_index.query(
            vector=emb,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        return [{
            "content": m.metadata.get("content", ""),
            "title": m.metadata.get("title", ""),
            "score": m.score
        } for m in results.matches]
    except Exception as e:
        logger.error(f"❌ Query error: {e}")
        return []