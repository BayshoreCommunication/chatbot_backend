"""
Knowledge Base Service with OpenAI Web Search Integration
Automatically gathers company information using OpenAI web search tools
Stores in MongoDB and Vector Database (Pinecone)
"""

import os
import logging
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Union, Set, Tuple
from datetime import datetime
from bson import ObjectId
from openai import OpenAI
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
    text: Optional[str] = None
) -> List[Document]:
    """
    Load and split document from file or text (PDFs and manual text only)
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

        elif text:
            documents = [Document(page_content=text, metadata={"source": "manual_input"})]

        # Split documents
        text_splitter = get_text_splitter()
        split_docs = text_splitter.split_documents(documents) 
        
        return split_docs
        
    except Exception as e:
        logger.error(f"Error loading/splitting document: {e}")
        return []

# ==========================================
# OPENAI WEB SEARCH FOR COMPANY INFO
# ==========================================

async def detect_business_type(company_name: str, website: Optional[str] = None) -> Dict[str, Any]:
    """
    STEP 1: Detect business type and industry to determine what information to collect
    """
    try:
        logger.info(f"🔍 STEP 1: Detecting business type for {company_name}...")
        
        search_query = f"{company_name} {website or ''} what type of business industry"
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analyst. Search the web and determine the business type, industry, and what information customers typically need from this type of business."
                },
                {
                    "role": "user",
                    "content": f"""Search the web for: {search_query}

Determine:
1. What type of business is this? (e.g., law firm, restaurant, retail store, medical practice, software company, real estate, consulting, etc.)
2. What industry/sector?
3. What are the TOP 8-10 most important pieces of information customers need from this type of business?

Return JSON format:
{{
  "businessType": "law firm / restaurant / retail / medical / software / consulting / etc.",
  "industry": "specific industry",
  "description": "brief description",
  "keyInformationNeeded": [
    "contact information",
    "business-specific item 1",
    "business-specific item 2",
    ...
  ]
}}"""
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
            temperature=0.2
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        logger.info(f"✅ Detected: {result.get('businessType', 'Unknown')} in {result.get('industry', 'Unknown')} industry")
        logger.info(f"📋 Key info needed: {', '.join(result.get('keyInformationNeeded', [])[:5])}...")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Business type detection failed: {e}")
        return {
            "businessType": "general business",
            "industry": "unknown",
            "keyInformationNeeded": [
                "contact information", "services", "team", "pricing", 
                "testimonials", "FAQs", "location", "hours"
            ]
        }

async def generate_search_queries(company_name: str, website: Optional[str], business_info: Dict[str, Any]) -> List[str]:
    """
    STEP 2: Generate UNLIMITED intelligent, business-specific search queries
    """
    try:
        logger.info(f"🔍 STEP 2: Generating UNLIMITED search queries for {business_info.get('businessType', 'business')}...")
        
        prompt = f"""Based on this business information, generate AS MANY search queries as needed (NO LIMIT) to collect COMPLETE and COMPREHENSIVE information about this business:

Business: {company_name}
Type: {business_info.get('businessType', 'unknown')}
Industry: {business_info.get('industry', 'unknown')}
Website: {website or 'N/A'}

Key Information Needed:
{json.dumps(business_info.get('keyInformationNeeded', []), indent=2)}

Generate COMPREHENSIVE search queries (15-25+ queries) that will find EVERYTHING:
- Company overview, history, mission, values
- EVERY team member with names, roles, experience, education
- Complete contact information (phone, email, address, hours, social media)
- ALL services/products offered with detailed descriptions
- Pricing/fees/costs for everything
- Process/how it works step-by-step
- Testimonials/reviews from multiple sources
- FAQs and common questions
- Industry-specific certifications, awards, recognition
- Locations, service areas, coverage
- Portfolio/case studies/examples of work
- Partnerships, affiliations
- Company culture, values, community involvement
- Technology, tools, methods used
- Guarantees, warranties, policies
- Booking/scheduling/ordering process
- Payment options, financing
- Emergency services (if applicable)
- Any other business-critical information

Return JSON array of search query strings:
{{
  "queries": [
    "query 1",
    "query 2",
    "query 3",
    ... (continue with ALL necessary queries)
  ]
}}

Make queries HIGHLY SPECIFIC to this business type. Generate AT LEAST 15-20 queries, more if needed.

Examples:
- Restaurant: menu items, chef biography, cuisine style, dietary options, reservations, delivery, takeout, catering, reviews, awards, hours, parking, dress code, private events
- Law firm: each practice area, each attorney with experience, case results, settlements, consultation process, fees, contingency, testimonials, awards, bar memberships
- Medical: every service, every doctor with specialties, insurance accepted, appointment booking, emergency care, hours, patient reviews, certifications, technology
- Retail: product categories, brands, pricing, shipping options, return policy, store locations, hours, sales, promotions, customer service, warranties"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at creating comprehensive, targeted web search queries. Generate as many queries as needed (no limit) to ensure complete information coverage."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        queries = result.get("queries", [])
        
        # Add site-specific queries if website provided
        if website:
            queries.insert(0, f"site:{website} about {company_name}")
            queries.insert(1, f"site:{website} team staff people")
            queries.insert(2, f"site:{website} contact location hours")
        
        logger.info(f"✅ Generated {len(queries)} search queries")
        return queries
        
    except Exception as e:
        logger.error(f"❌ Query generation failed: {e}")
        # Fallback to comprehensive generic queries
        return [
            f"{company_name} official website overview history mission",
            f"{company_name} team staff members employees leadership",
            f"{company_name} contact information phone email address",
            f"{company_name} services products offerings details",
            f"{company_name} pricing fees costs rates",
            f"{company_name} reviews testimonials client feedback",
            f"{company_name} FAQ frequently asked questions",
            f"{company_name} locations service areas coverage",
            f"{company_name} process how it works booking",
            f"{company_name} certifications awards recognition",
            f"{company_name} portfolio case studies examples",
            f"{company_name} hours availability schedule",
            f"{company_name} payment options financing",
            f"{company_name} policies guarantees warranties",
            f"{company_name} community involvement social responsibility"
        ]

async def search_company_with_openai(company_name: str, website: Optional[str] = None) -> Dict[str, Any]:
    """
    INTELLIGENT WEB SEARCH: Adapts to any business type
    
    STEP 1: Detect business type and industry
    STEP 2: Generate business-specific search queries
    STEP 3: Execute searches and collect comprehensive information
    """
    try:
        logger.info(f"🚀 Starting INTELLIGENT web search for {company_name}...")
        
        # STEP 1: Detect business type
        business_info = await detect_business_type(company_name, website)
        
        # STEP 2: Generate adaptive search queries
        search_queries = await generate_search_queries(company_name, website, business_info)
        
        # STEP 3: Execute searches
        logger.info(f"🔍 STEP 3: Executing {len(search_queries)} searches...")
        all_results = []
        
        for idx, query in enumerate(search_queries, 1):
            try:
                logger.info(f"  🔎 [{idx}/{len(search_queries)}] {query}")
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a research assistant specializing in {business_info.get('industry', 'business')} industry. Search the web and provide comprehensive, accurate information. Include specific details like names, numbers, dates, and direct quotes."
                        },
                        {
                            "role": "user",
                            "content": f"Search the web and provide detailed information about: {query}\n\nBusiness Context: {company_name} is a {business_info.get('businessType', 'business')}\n\nInclude:\n- Specific names, roles, and experience (e.g., 'John Smith, 10+ years')\n- Exact contact details\n- Detailed descriptions\n- Pricing/costs if mentioned\n- Direct quotes from official sources\n- Any unique or standout information"
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.2
                )
                
                result = response.choices[0].message.content
                if result:
                    all_results.append({
                        "query": query,
                        "content": result
                    })
                    logger.info(f"    ✅ Found: {len(result)} chars")
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"    ⚠️ Search failed: {e}")
                continue
        
        # Combine all results
        combined_content = f"=== INTELLIGENT WEB SEARCH RESULTS ===\n\n"
        combined_content += f"Business: {company_name}\n"
        combined_content += f"Type: {business_info.get('businessType', 'Unknown')}\n"
        combined_content += f"Industry: {business_info.get('industry', 'Unknown')}\n\n"
        combined_content += "=" * 50 + "\n\n"
        
        for result in all_results:
            combined_content += f"\n## Query: {result['query']}\n{result['content']}\n\n---\n\n"
        
        logger.info(f"✅ Collected {len(all_results)}/{len(search_queries)} search results ({len(combined_content)} chars)")
        
        return {
            "combined_content": combined_content,
            "search_results": all_results,
            "business_type": business_info.get("businessType"),
            "industry": business_info.get("industry"),
            "total_queries": len(search_queries),
            "successful_queries": len(all_results)
        }
        
    except Exception as e:
        logger.error(f"❌ Error in OpenAI web search: {e}")
        return {
            "combined_content": f"Error searching for {company_name}",
            "search_results": [],
            "total_queries": 0,
            "successful_queries": 0
        }

# ==========================================
# AUTO-BUILD LOGIC
# ==========================================

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

async def extract_structured_data(combined_content: str, company_name: str, website: Optional[str] = None, business_type: str = "business", industry: str = "general") -> Dict[str, Any]:
    """Extract structured data from raw content using OpenAI (business-type aware)"""
    try:
        logger.info(f"🧠 Extracting structured data for {company_name} ({business_type})...")
        enhanced_prompt = f"""You are an expert at extracting and structuring {business_type} information for AI chatbot use in the {industry} industry.
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
  "team": [{
    "name": "Full Name",
    "role": "Attorney/Partner/Associate/Position",
    "experienceYears": "10+",
    "education": "Degree, University",
    "specializations": ["Personal Injury", "Car Accidents"],
    "bio": "Full biography with specific details"
  }],
  "testimonials": [{"text": "...", "author": "..."}],
  "processSteps": [{"step": 1, "title": "...", "description": "..."}],
  "chatbotResponses": {"greeting": "...", "callToAction": "..."}
}

IMPORTANT FOR TEAM MEMBERS:
- Extract EVERY individual person mentioned (attorneys, staff, partners)
- Include full names (e.g., "David Carter", not just "Carter")
- Capture years of experience (e.g., "10+ years", "5 years")
- Include education and credentials
- Extract full biographies with specific achievements
- If text says "David Carter has 10 years experience", capture: {"name": "David Carter", "experienceYears": "10+", "bio": "..."}

Use null for missing fields. Be comprehensive and specific."""
        
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

    # Team Members (NEW: Individual attorney profiles)
    team = structured_data.get("team", [])
    if isinstance(team, list):
        for member in team:
            if isinstance(member, dict) and member.get("name"):
                team_content = f"{member.get('name')} - {member.get('role', 'Team Member')}\n\n"
                
                if member.get("experienceYears"):
                    team_content += f"Experience: {member['experienceYears']}\n"
                if member.get("education"):
                    team_content += f"Education: {member['education']}\n"
                if member.get("specializations"):
                    team_content += f"Specializations: {', '.join(member['specializations'])}\n"
                if member.get("bio"):
                    team_content += f"\n{member['bio']}"
                
                chunks.append({
                    "type": "team_member",
                    "title": f"{member.get('name')} - {member.get('role', 'Team Member')}",
                    "content": team_content.strip(),
                    "metadata": {"use_for": ["team", "attorney", "staff", "about", member.get('name', '').lower()]}
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
    text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified function to add any document type to the Knowledge Base.
    Handles Text and PDFs only (no web scraping).
    """
    try:
        # 1. Load and Split
        split_docs = await load_and_split_document(file_path, text)
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
            "type": "document" if file_path else "manual",
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
    """Enhanced auto-build using OpenAI web search (no BeautifulSoup scraping)"""
    try:
        logger.info(f"🚀 Building knowledge base for {company_name} using OpenAI Web Search")
        
        # 1. USE OPENAI WEB SEARCH TO GATHER ALL COMPANY INFO
        search_data = await search_company_with_openai(company_name, website)
        combined_content = search_data.get("combined_content", "")
        search_results = search_data.get("search_results", [])
        
        if not combined_content or len(combined_content) < 100:
            raise Exception("No content found from web search")
        
        sources = []
        for result in search_results:
            sources.append({
                "type": "web_search",
                "query": result.get("query", ""),
                "content": result.get("content", "")[:500]
            })
        
        logger.info(f"✅ Collected data from {len(search_results)} web searches")
        
        # Get business type for better extraction
        business_type = search_data.get("business_type", "business")
        industry = search_data.get("industry", "general")
        logger.info(f"📊 Processing as: {business_type} in {industry} industry")
        
        # 2. Extract Structure with GPT-4o (business-aware)
        structured = await extract_structured_data(combined_content, company_name, website, business_type, industry)
        
        # 3. DETECT GAPS & COMPLETENESS SCORE
        gaps = await detect_missing_info(structured, company_name)
        completeness_score = gaps.get("confidence_score", 50)
        
        # 6. Create Chunks (includes individual team member profiles)
        chunks = create_chatbot_chunks(structured, company_name)
        logger.info(f"📦 Created {len(chunks)} chatbot chunks")
        
        # 7. Store in Vector DB
        namespace = await store_chunks_in_vector_db(chunks, user_id, organization_id, company_name)
        
        # 7. Save/Update MongoDB with enhanced metadata
        kb_data = {
            "userId": user_id,
            "organizationId": organization_id,
            "companyName": company_name,
            "website": website,
            "sources": sources,
            "structuredData": structured,
            "aiChunks": chunks,
            "vectorStoreId": namespace,
            "status": "active",
            "businessType": search_data.get("business_type", "unknown"),
            "industry": search_data.get("industry", "unknown"),
            "metadata": {
                "totalSources": len(sources),
                "totalChunks": len(chunks),
                "webSearchQueries": search_data.get("successful_queries", 0),
                "completenessScore": completeness_score,
                "missingInfo": gaps.get("missing_critical", []),
                "lastUpdated": datetime.now(),
                "method": "intelligent_web_search",
                "model": "gpt-4o",
                "quality": "high" if completeness_score >= 80 else "medium" if completeness_score >= 60 else "low"
            },
            "updatedAt": datetime.now(),
            "createdAt": datetime.now()
        }
        
        logger.info(f"✅ Knowledge base built using OpenAI Web Search: {len(sources)} sources, {len(chunks)} chunks, {completeness_score}% complete")
        
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