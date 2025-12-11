"""
Knowledge Base Service with OpenAI Web Search Integration
Automatically gathers company information using OpenAI web search tools
Stores in MongoDB and Vector Database (Pinecone)
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from openai import OpenAI
import requests
from bs4 import BeautifulSoup

from services.database import db

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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


# Enhanced system prompt for knowledge extraction
KNOWLEDGE_EXTRACTION_PROMPT = """You are an expert AI assistant specialized in extracting and structuring company information.

Analyze the web search results and website content to extract comprehensive information about the company.

Extract the following in a clear, structured JSON format:

{
  "companyOverview": "A comprehensive overview of the company (2-3 paragraphs)",
  "services": ["Service 1", "Service 2", ...],
  "products": ["Product 1", "Product 2", ...],
  "contactInfo": {
    "email": "contact@example.com",
    "phone": "+1234567890",
    "address": "Full address",
    "socialMedia": {
      "linkedin": "URL",
      "twitter": "URL",
      "facebook": "URL"
    }
  },
  "keyFeatures": ["Feature 1", "Feature 2", ...],
  "pricing": "Pricing information if available",
  "faqs": [
    {"question": "Q1?", "answer": "A1"},
    {"question": "Q2?", "answer": "A2"}
  ],
  "additionalInfo": {
    "mission": "Company mission",
    "values": ["Value 1", "Value 2"],
    "achievements": ["Achievement 1", "Achievement 2"],
    "teamSize": "Number of employees",
    "foundedYear": "Year",
    "industries": ["Industry 1", "Industry 2"]
  }
}

Instructions:
- Extract ONLY factual information present in the content
- Use null for missing information instead of guessing
- Be comprehensive but concise
- Organize information logically
- Focus on information useful for customer support and sales
- Return valid JSON only"""


async def scrape_website(url: str) -> str:
    """
    Scrape website content using BeautifulSoup
    
    Args:
        url: Website URL to scrape
        
    Returns:
        Cleaned text content from website
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe']):
            element.decompose()
        
        # Extract text content
        content = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        content = ' '.join(content.split())
        
        logger.info(f"✅ Successfully scraped {url} ({len(content)} characters)")
        return content[:10000]  # Limit to 10k characters
        
    except Exception as e:
        logger.error(f"❌ Error scraping {url}: {e}")
        return ""


async def perform_web_search(company_name: str, website: Optional[str] = None) -> str:
    """
    Use GPT-4o to analyze and expand website content with additional context
    Note: OpenAI Chat API doesn't support direct web search
    
    Args:
        company_name: Name of the company
        website: Optional website URL to focus search
        
    Returns:
        Enhanced analysis of company information
    """
    try:
        logger.info(f"🔍 Using GPT-4o to enhance company data for: {company_name}")
        
        # Use GPT-4o to generate comprehensive questions/info about the company
        # This helps structure the extraction better
        prompt = f"""Based on the company name "{company_name}" and website "{website if website else 'unknown'}", 
generate a comprehensive analysis framework covering:

1. What type of business/services they likely offer
2. Common questions customers might ask
3. Standard contact information needed
4. Typical pricing structures for this industry
5. Key features customers look for
6. Process/workflow expectations

Provide this as a structured guide for information extraction."""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert business analyst. Generate comprehensive analysis frameworks for understanding companies."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2048,
            temperature=0.3
        )
        
        result = response.choices[0].message.content or ""
        logger.info(f"✅ Generated analysis framework ({len(result)} chars)")
        return result
        
    except Exception as e:
        logger.error(f"❌ Analysis generation failed: {e}")
        return ""


async def extract_structured_data(
    combined_content: str,
    company_name: str,
    website: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract structured data from raw content using OpenAI
    Optimized for AI chatbot responses with detailed, conversational format
    
    Args:
        combined_content: Combined content from all sources
        company_name: Name of the company
        website: Company website URL
        
    Returns:
        Structured data dictionary optimized for chatbot use
    """
    try:
        logger.info(f"🧠 Extracting structured data for {company_name}...")
        
        enhanced_prompt = """You are an expert at extracting and structuring company information for AI chatbot use.

Extract comprehensive, chatbot-friendly information in this exact JSON format:

{
  "companyOverview": "Detailed 2-3 paragraph overview written conversationally. Include what the company does, their mission, values, and what makes them unique.",
  "tagline": "Main company tagline or slogan",
  "serviceAreas": {
    "geographic": ["City 1", "City 2", "State", "Region"],
    "industries": ["Industry 1", "Industry 2"]
  },
  "services": [
    {
      "name": "Service Name",
      "description": "Detailed description of what this service includes and who it helps",
      "keywords": ["keyword1", "keyword2"]
    }
  ],
  "products": [
    {
      "name": "Product Name",
      "description": "What this product offers and its benefits"
    }
  ],
  "contactInfo": {
    "phone": "Phone number with formatting",
    "email": "Email address",
    "address": "Full address",
    "website": "Website URL",
    "availability": "Hours/availability info (e.g., '24/7', 'Mon-Fri 9-5')",
    "socialMedia": {
      "facebook": "URL",
      "linkedin": "URL",
      "twitter": "URL",
      "instagram": "URL"
    }
  },
  "keyFeatures": [
    {
      "feature": "Feature name",
      "description": "Why this matters to customers"
    }
  ],
  "pricing": {
    "structure": "How pricing works (e.g., 'contingency fee', 'hourly', 'fixed')",
    "details": "Specific pricing details",
    "freeServices": ["Free consultation", "Free evaluation"],
    "paymentTerms": "Payment terms explanation"
  },
  "faqs": [
    {
      "question": "Common question customers ask",
      "answer": "Detailed, helpful answer in conversational tone",
      "category": "Category (e.g., 'pricing', 'services', 'process')"
    }
  ],
  "caseResults": [
    {
      "type": "Case type",
      "result": "Settlement/outcome amount or description",
      "description": "Brief case description"
    }
  ],
  "team": [
    {
      "name": "Team member name",
      "role": "Position/title",
      "description": "Background and expertise"
    }
  ],
  "testimonials": [
    {
      "text": "Client testimonial text",
      "author": "Client name or Anonymous",
      "rating": 5
    }
  ],
  "processSteps": [
    {
      "step": 1,
      "title": "Step title",
      "description": "What happens in this step"
    }
  ],
  "additionalInfo": {
    "mission": "Company mission statement",
    "values": ["Value 1", "Value 2"],
    "certifications": ["Certification 1"],
    "awards": ["Award 1"],
    "yearsInBusiness": "Number or founding year",
    "teamSize": "Number of employees/attorneys/staff",
    "languages": ["English", "Spanish"],
    "areasServed": ["Area 1", "Area 2"],
    "specializations": ["Specialization 1"]
  },
  "chatbotResponses": {
    "greeting": "How the chatbot should greet users",
    "callToAction": "Main CTA text",
    "emergencyMessage": "Message for urgent situations",
    "officeClosedMessage": "After-hours message"
  }
}

IMPORTANT:
- Write ALL text in natural, conversational language suitable for chatbot responses
- Be comprehensive - extract every piece of useful information
- Format phone numbers, addresses, and URLs properly
- Group related information logically
- Include context that helps the chatbot understand intent
- Extract actual testimonials and case results if available
- Use null for missing fields, never guess or make up information"""
        
        response = client.chat.completions.create(
            model="gpt-4o",  # Latest GPT-4o model
            messages=[
                {
                    "role": "system",
                    "content": enhanced_prompt
                },
                {
                    "role": "user",
                    "content": f"Company: {company_name}\nWebsite: {website or 'N/A'}\n\nCollected Information:\n{combined_content[:30000]}\n\nExtract and structure ALL relevant information in the JSON format specified. Be thorough and comprehensive."
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Lower temperature for more consistent extraction
            max_tokens=4096  # Allow comprehensive extraction
        )
        
        structured_data = response.choices[0].message.content or "{}"
        
        # Parse JSON response
        import json
        structured_data = json.loads(structured_data)
        
        logger.info(f"✅ Structured data extracted successfully")
        return structured_data
        
    except Exception as e:
        logger.error(f"❌ Error extracting structured data: {e}")
        return {
            "companyOverview": combined_content[:500],
            "services": [],
            "products": [],
            "contactInfo": {},
            "keyFeatures": [],
            "pricing": {},
            "faqs": [],
            "additionalInfo": {}
        }


def create_chatbot_chunks(
    structured_data: Dict[str, Any],
    company_name: str
) -> List[Dict[str, Any]]:
    """
    Create AI-friendly chunks optimized for chatbot responses
    Each chunk is self-contained and conversational
    
    Args:
        structured_data: Structured company data
        company_name: Company name
        
    Returns:
        List of chatbot-ready chunks
    """
    chunks = []
    
    # Chunk 1: Company Overview & Introduction
    if structured_data.get("companyOverview"):
        chunks.append({
            "type": "company_overview",
            "title": f"About {company_name}",
            "content": structured_data["companyOverview"],
            "metadata": {
                "tagline": structured_data.get("tagline"),
                "use_for": ["general_inquiry", "company_info", "introduction"]
            }
        })
    
    # Chunk 2: Contact Information (Critical for chatbot)
    contact = structured_data.get("contactInfo", {})
    if contact:
        contact_text = f"You can reach {company_name} at:\n"
        if contact.get("phone"):
            contact_text += f"📞 Phone: {contact['phone']}"
            if contact.get("availability"):
                contact_text += f" ({contact['availability']})"
            contact_text += "\n"
        if contact.get("email"):
            contact_text += f"📧 Email: {contact['email']}\n"
        if contact.get("address"):
            contact_text += f"📍 Address: {contact['address']}\n"
        if contact.get("website"):
            contact_text += f"🌐 Website: {contact['website']}\n"
        
        chunks.append({
            "type": "contact_info",
            "title": f"Contact {company_name}",
            "content": contact_text.strip(),
            "metadata": {
                "phone": contact.get("phone"),
                "email": contact.get("email"),
                "use_for": ["contact", "phone", "email", "address", "location", "hours"]
            }
        })
    
    # Chunk 3: Services (One chunk per service for better retrieval)
    services = structured_data.get("services", [])
    if isinstance(services, list):
        for idx, service in enumerate(services):
            if isinstance(service, dict):
                service_text = f"{company_name} offers {service.get('name', 'this service')}.\n\n"
                if service.get("description"):
                    service_text += service["description"]
                
                chunks.append({
                    "type": "service",
                    "title": service.get("name", f"Service {idx + 1}"),
                    "content": service_text,
                    "metadata": {
                        "keywords": service.get("keywords", []),
                        "use_for": ["services", "what_we_do", "offerings"]
                    }
                })
            elif isinstance(service, str):
                chunks.append({
                    "type": "service",
                    "title": service,
                    "content": f"{company_name} provides {service}.",
                    "metadata": {
                        "use_for": ["services", "what_we_do"]
                    }
                })
    
    # Chunk 4: Pricing Information
    pricing = structured_data.get("pricing", {})
    if isinstance(pricing, dict) and pricing:
        pricing_text = f"Pricing at {company_name}:\n\n"
        if pricing.get("structure"):
            pricing_text += f"Structure: {pricing['structure']}\n"
        if pricing.get("details"):
            pricing_text += f"\n{pricing['details']}\n"
        if pricing.get("freeServices"):
            pricing_text += f"\nFree Services: {', '.join(pricing['freeServices'])}\n"
        if pricing.get("paymentTerms"):
            pricing_text += f"\nPayment Terms: {pricing['paymentTerms']}"
        
        chunks.append({
            "type": "pricing",
            "title": "Pricing & Fees",
            "content": pricing_text.strip(),
            "metadata": {
                "use_for": ["pricing", "cost", "fees", "payment", "free"]
            }
        })
    elif isinstance(pricing, str):
        chunks.append({
            "type": "pricing",
            "title": "Pricing & Fees",
            "content": pricing,
            "metadata": {
                "use_for": ["pricing", "cost", "fees"]
            }
        })
    
    # Chunk 5: FAQs (Each FAQ as separate chunk for precise answers)
    faqs = structured_data.get("faqs", [])
    if isinstance(faqs, list):
        for faq in faqs:
            if isinstance(faq, dict) and faq.get("question") and faq.get("answer"):
                chunks.append({
                    "type": "faq",
                    "title": faq["question"],
                    "content": f"Q: {faq['question']}\n\nA: {faq['answer']}",
                    "metadata": {
                        "category": faq.get("category", "general"),
                        "use_for": ["faq", "questions", faq.get("category", "general")]
                    }
                })
    
    # Chunk 6: Process/Steps
    process = structured_data.get("processSteps", [])
    if isinstance(process, list) and process:
        process_text = f"How {company_name} works:\n\n"
        for step in process:
            if isinstance(step, dict):
                process_text += f"Step {step.get('step', '')}: {step.get('title', '')}\n"
                if step.get("description"):
                    process_text += f"{step['description']}\n\n"
        
        chunks.append({
            "type": "process",
            "title": "Our Process",
            "content": process_text.strip(),
            "metadata": {
                "use_for": ["process", "how_it_works", "steps", "procedure"]
            }
        })
    
    # Chunk 7: Testimonials & Social Proof
    testimonials = structured_data.get("testimonials", [])
    if isinstance(testimonials, list) and testimonials:
        testimonial_text = f"What clients say about {company_name}:\n\n"
        for idx, testimonial in enumerate(testimonials[:5], 1):  # Limit to 5
            if isinstance(testimonial, dict):
                testimonial_text += f"{idx}. "
                if testimonial.get("rating"):
                    testimonial_text += f"{'⭐' * int(testimonial['rating'])} "
                testimonial_text += f"\"{testimonial.get('text', '')}\""
                if testimonial.get("author"):
                    testimonial_text += f" - {testimonial['author']}"
                testimonial_text += "\n\n"
        
        chunks.append({
            "type": "testimonials",
            "title": "Client Testimonials",
            "content": testimonial_text.strip(),
            "metadata": {
                "use_for": ["reviews", "testimonials", "feedback", "reputation"]
            }
        })
    
    # Chunk 8: Team Information
    team = structured_data.get("team", [])
    if isinstance(team, list) and team:
        team_text = f"Meet the {company_name} team:\n\n"
        for member in team:
            if isinstance(member, dict):
                team_text += f"• {member.get('name', '')} - {member.get('role', '')}\n"
                if member.get("description"):
                    team_text += f"  {member['description']}\n\n"
        
        chunks.append({
            "type": "team",
            "title": "Our Team",
            "content": team_text.strip(),
            "metadata": {
                "use_for": ["team", "staff", "attorneys", "people", "who"]
            }
        })
    
    # Chunk 9: Case Results/Achievements
    results = structured_data.get("caseResults", [])
    if isinstance(results, list) and results:
        results_text = f"{company_name} results:\n\n"
        for result in results:
            if isinstance(result, dict):
                results_text += f"• {result.get('type', 'Case')}: {result.get('result', '')}\n"
                if result.get("description"):
                    results_text += f"  {result['description']}\n"
        
        chunks.append({
            "type": "results",
            "title": "Case Results",
            "content": results_text.strip(),
            "metadata": {
                "use_for": ["results", "outcomes", "settlements", "wins"]
            }
        })
    
    # Chunk 10: Chatbot-specific responses
    chatbot_responses = structured_data.get("chatbotResponses", {})
    if chatbot_responses:
        chunks.append({
            "type": "chatbot_config",
            "title": "Chatbot Configuration",
            "content": str(chatbot_responses),
            "metadata": {
                "greeting": chatbot_responses.get("greeting"),
                "cta": chatbot_responses.get("callToAction"),
                "use_for": ["greeting", "cta", "emergency"]
            }
        })
    
    logger.info(f"✅ Created {len(chunks)} AI-friendly chunks")
    return chunks


async def store_chunks_in_vector_db(
    chunks: List[Dict[str, Any]],
    user_id: str,
    organization_id: str,
    company_name: str
) -> str:
    """
    Store AI chunks in Pinecone vector database with embeddings
    
    Args:
        chunks: List of AI-friendly chunks
        user_id: User ID
        organization_id: Organization ID  
        company_name: Company name
        
    Returns:
        Namespace used in Pinecone (serves as vector_store_id)
    """
    try:
        if not pinecone_index:
            logger.error("❌ Pinecone index is None - check PINECONE_API_KEY and PINECONE_INDEX environment variables")
            logger.error(f"   PINECONE_API_KEY exists: {bool(os.getenv('PINECONE_API_KEY'))}")
            logger.error(f"   PINECONE_INDEX: {os.getenv('PINECONE_INDEX', 'bayai')}")
            return None
        
        # Create unique namespace for this organization
        namespace = f"kb_{organization_id}"
        
        logger.info(f"📤 Storing {len(chunks)} chunks in Pinecone (namespace: {namespace})...")
        
        vectors_to_upsert = []
        
        for i, chunk in enumerate(chunks):
            # Get embedding for chunk content
            embedding_response = client.embeddings.create(
                model="text-embedding-3-small",
                input=chunk["content"],
                dimensions=1024  # Match Pinecone index dimension
            )
            embedding = embedding_response.data[0].embedding
            
            # Prepare vector data
            vector_id = f"kb_{user_id}_{organization_id}_{chunk['type']}_{i}"
            
            vectors_to_upsert.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "company_name": company_name,
                    "chunk_type": chunk["type"],
                    "title": chunk["title"],
                    "content": chunk["content"][:1000],  # Limit metadata size
                    "use_for": ",".join(chunk["metadata"].get("use_for", []))
                }
            })
        
        # Upsert to Pinecone in batch
        pinecone_index.upsert(
            vectors=vectors_to_upsert,
            namespace=namespace
        )
        
        logger.info(f"✅ Stored {len(vectors_to_upsert)} vectors in Pinecone")
        return namespace
        
    except Exception as e:
        logger.error(f"❌ Error storing chunks in vector DB: {e}")
        return None


def calculate_quality_score(
    structured_data: Dict[str, Any],
    source_count: int
) -> tuple[str, float]:
    """
    Calculate quality score and percentage based on chatbot-ready completeness
    
    Args:
        structured_data: Structured company data
        source_count: Number of sources collected
        
    Returns:
        Tuple of (quality_level, quality_percentage)
    """
    score = 0
    max_score = 130  # Total possible points
    
    # Core information (40 points)
    if structured_data.get("companyOverview") and len(structured_data.get("companyOverview", "")) > 100:
        score += 20
    elif structured_data.get("companyOverview"):
        score += 10
        
    if structured_data.get("tagline"):
        score += 5
        
    if structured_data.get("serviceAreas"):
        score += 5
        
    if structured_data.get("chatbotResponses"):
        score += 10
    
    # Services and products (25 points)
    services = structured_data.get("services", [])
    if isinstance(services, list) and len(services) > 0:
        if any(isinstance(s, dict) and s.get("description") for s in services):
            score += 15  # Detailed services
        else:
            score += 8   # Basic services list
    
    products = structured_data.get("products", [])
    if isinstance(products, list) and len(products) > 0:
        score += 10
    
    # Contact information (25 points)
    contact = structured_data.get("contactInfo", {})
    if contact.get("phone"):
        score += 8
    if contact.get("email"):
        score += 7
    if contact.get("address"):
        score += 5
    if contact.get("availability"):
        score += 5
    
    # Interactive content (30 points)
    faqs = structured_data.get("faqs", [])
    if isinstance(faqs, list) and len(faqs) >= 5:
        score += 15
    elif isinstance(faqs, list) and len(faqs) > 0:
        score += 8
    
    if structured_data.get("testimonials") and len(structured_data.get("testimonials", [])) > 0:
        score += 8
        
    if structured_data.get("processSteps") and len(structured_data.get("processSteps", [])) > 0:
        score += 7
    
    # Additional valuable info (10 points)
    if structured_data.get("pricing") and isinstance(structured_data.get("pricing"), dict):
        score += 5
    if structured_data.get("team") and len(structured_data.get("team", [])) > 0:
        score += 5
    
    # Bonus for multiple sources and completeness
    if source_count >= 3:
        score += 10
    elif source_count >= 2:
        score += 5
    
    # Calculate percentage
    percentage = min(int((score / max_score) * 100), 100)
    
    # Determine quality level
    if percentage >= 75:
        quality = "high"
    elif percentage >= 50:
        quality = "medium"
    else:
        quality = "low"
    
    return quality, percentage


async def build_knowledge_base_auto(
    user_id: str,
    organization_id: str,
    company_name: str,
    website: Optional[str] = None
) -> Dict[str, Any]:
    """
    Automatically build knowledge base using OpenAI web search
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        company_name: Company name
        website: Optional company website URL
        
    Returns:
        Created/updated knowledge base document
    """
    try:
        logger.info(f"🚀 Building knowledge base for {company_name}")
        logger.info(f"🔍 Pinecone status: {'Available' if pinecone_index else 'NOT AVAILABLE'}")
        
        # Check if knowledge base already exists
        existing_kb = knowledge_bases.find_one({
            "userId": ObjectId(user_id),
            "status": {"$ne": "archived"}
        })
        
        sources = []
        combined_content = ""
        
        # Step 1: Scrape primary website if provided
        if website:
            logger.info(f"📄 Scraping website: {website}")
            website_content = await scrape_website(website)
            
            if website_content:
                sources.append({
                    "type": "website",
                    "url": website,
                    "content": website_content,
                    "processedAt": datetime.now()
                })
                combined_content += f"\n\n=== WEBSITE ({website}) ===\n{website_content}"
        
        # Step 2: Generate analysis framework using GPT-4o
        logger.info(f"🔍 Generating analysis framework...")
        analysis_framework = await perform_web_search(company_name, website)
        
        if analysis_framework:
            sources.append({
                "type": "analysis",
                "searchQuery": f"Analysis framework for {company_name}",
                "content": analysis_framework,
                "processedAt": datetime.now()
            })
            combined_content += f"\n\n=== ANALYSIS FRAMEWORK ===\n{analysis_framework}"
        
        if not combined_content or len(combined_content) < 100:
            raise Exception("Failed to gather sufficient information")
        
        # Step 3: Extract structured data using OpenAI
        logger.info(f"🧠 Extracting structured information...")
        structured_data = await extract_structured_data(combined_content, company_name, website)
        
        # Step 4: Calculate quality score
        quality, quality_percentage = calculate_quality_score(
            structured_data,
            len(sources)
        )
        
        logger.info(f"📊 Quality: {quality} ({quality_percentage}%)")
        
        # Step 5: Create AI-friendly chunks for chatbot
        logger.info(f"📦 Creating AI-friendly knowledge chunks...")
        ai_chunks = create_chatbot_chunks(structured_data, company_name)
        
        # Step 6: Store chunks in vector database (Pinecone)
        logger.info(f"💾 Storing chunks in vector database...")
        vector_store_id = await store_chunks_in_vector_db(
            ai_chunks,
            user_id,
            organization_id,
            company_name
        )
        
        if vector_store_id:
            logger.info(f"✅ Vector storage successful - ID: {vector_store_id}")
        else:
            logger.warning(f"⚠️ Vector storage failed - continuing without vector DB")
        
        # Step 7: Prepare knowledge base data
        now = datetime.now()
        
        if existing_kb:
            # Update existing
            version = existing_kb.get("metadata", {}).get("version", 1) + 1
            
            # Merge sources
            existing_sources = existing_kb.get("sources", [])
            all_sources = existing_sources + sources
            
            update_data = {
                "companyName": company_name,
                "sources": all_sources,
                "structuredData": structured_data,
                "rawContent": combined_content,
                "aiChunks": ai_chunks,  # Updated AI-friendly chunks
                "vectorStoreId": vector_store_id,  # Pinecone namespace
                "status": "active",
                "updatedAt": now,
                "metadata": {
                    "totalSources": len(all_sources),
                    "totalChunks": len(ai_chunks),
                    "lastUpdated": now,
                    "version": version,
                    "model": "gpt-4o",
                    "tokenCount": len(combined_content) // 4,
                    "quality": quality,
                    "qualityPercentage": quality_percentage,
                    "updateHistory": existing_kb.get("metadata", {}).get("updateHistory", []) + [{
                        "version": version,
                        "updatedAt": now,
                        "totalSources": len(all_sources),
                        "totalChunks": len(ai_chunks),
                        "quality": quality,
                        "qualityPercentage": quality_percentage,
                        "changes": f"Updated with {len(sources)} new sources and {len(ai_chunks)} AI chunks"
                    }]
                }
            }
            
            knowledge_bases.update_one(
                {"_id": existing_kb["_id"]},
                {"$set": update_data}
            )
            
            kb_data = {**existing_kb, **update_data}
            logger.info(f"✅ Knowledge base updated (ID: {existing_kb['_id']})")
            
        else:
            # Create new
            kb_data = {
                "userId": ObjectId(user_id),
                "organizationId": ObjectId(organization_id),
                "companyName": company_name,
                "sources": sources,
                "structuredData": structured_data,
                "rawContent": combined_content,
                "aiChunks": ai_chunks,  # AI-friendly chunks for chatbot
                "vectorStoreId": vector_store_id,  # Pinecone namespace where vectors are stored
                "fileIds": [],
                "metadata": {
                    "totalSources": len(sources),
                    "totalChunks": len(ai_chunks),
                    "lastUpdated": now,
                    "version": 1,
                    "model": "gpt-4o",
                    "tokenCount": len(combined_content) // 4,
                    "quality": quality,
                    "qualityPercentage": quality_percentage,
                    "updateHistory": [{
                        "version": 1,
                        "updatedAt": now,
                        "totalSources": len(sources),
                        "totalChunks": len(ai_chunks),
                        "quality": quality,
                        "qualityPercentage": quality_percentage,
                        "changes": "Initial knowledge base creation"
                    }]
                },
                "status": "active",
                "createdAt": now,
                "updatedAt": now
            }
            
            result = knowledge_bases.insert_one(kb_data)
            kb_data["_id"] = result.inserted_id
            logger.info(f"✅ Knowledge base created (ID: {result.inserted_id})")
        
        return kb_data
        
    except Exception as e:
        logger.error(f"❌ Error building knowledge base: {e}")
        raise


async def query_vector_db(
    query: str,
    organization_id: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Query Pinecone vector database for similar chunks
    
    Args:
        query: Search query
        organization_id: Organization ID
        top_k: Number of results to return
        
    Returns:
        List of similar chunks with scores
    """
    try:
        if not pinecone_index:
            logger.warning("⚠️ Pinecone not available")
            return []
        
        namespace = f"kb_{organization_id}"
        
        # Get query embedding
        embedding_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
            dimensions=1024  # Match Pinecone index dimension
        )
        query_embedding = embedding_response.data[0].embedding
        
        # Query Pinecone
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        # Format results
        chunks = []
        for match in results.matches:
            chunks.append({
                "content": match.metadata.get("content", ""),
                "title": match.metadata.get("title", ""),
                "type": match.metadata.get("chunk_type", ""),
                "score": match.score,
                "use_for": match.metadata.get("use_for", "").split(",")
            })
        
        logger.info(f"✅ Found {len(chunks)} similar chunks in vector DB")
        return chunks
        
    except Exception as e:
        logger.error(f"❌ Error querying vector DB: {e}")
        return []


async def get_chatbot_chunks_by_intent(
    user_id: str,
    organization_id: str,
    intent: str
) -> List[Dict[str, Any]]:
    """
    Get AI chunks filtered by intent/purpose for chatbot responses
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        intent: Intent category (e.g., 'contact', 'services', 'pricing')
        
    Returns:
        List of relevant chunks for the intent
    """
    try:
        kb = knowledge_bases.find_one({
            "userId": ObjectId(user_id),
            "status": "active"
        })
        
        if not kb or not kb.get("aiChunks"):
            return []
        
        # Filter chunks by intent
        relevant_chunks = []
        for chunk in kb["aiChunks"]:
            use_for = chunk.get("metadata", {}).get("use_for", [])
            if intent.lower() in [u.lower() for u in use_for]:
                relevant_chunks.append(chunk)
        
        logger.info(f"✅ Found {len(relevant_chunks)} chunks for intent: {intent}")
        return relevant_chunks
        
    except Exception as e:
        logger.error(f"❌ Error getting chatbot chunks: {e}")
        return []


async def get_all_chatbot_context(
    user_id: str,
    organization_id: str
) -> str:
    """
    Get complete chatbot context as formatted text
    Useful for passing to AI assistant as system context
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        
    Returns:
        Formatted context string for AI assistant
    """
    try:
        kb = knowledge_bases.find_one({
            "userId": ObjectId(user_id),
            "status": "active"
        })
        
        if not kb:
            return "No knowledge base found."
        
        context = f"=== KNOWLEDGE BASE: {kb.get('companyName')} ===\n\n"
        
        ai_chunks = kb.get("aiChunks", [])
        for chunk in ai_chunks:
            context += f"## {chunk.get('title', 'Information')}\n"
            context += f"{chunk.get('content', '')}\n\n"
            context += "---\n\n"
        
        logger.info(f"✅ Generated complete chatbot context ({len(context)} characters)")
        return context
        
    except Exception as e:
        logger.error(f"❌ Error getting chatbot context: {e}")
        return "Error loading knowledge base."
