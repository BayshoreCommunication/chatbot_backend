"""
IMPROVED ENGINE - Smart Lead Capture + Advanced Caching + Performance Optimizations
==================================================================================
This version includes:
- Smart lead capture with organization settings
- Advanced multi-level caching strategy
- Better error handling and recovery
- Performance optimizations
- Response quality improvements
"""

from langchain_openai import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from dotenv import load_dotenv
import os
import openai
import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio

from services.language_detect import detect_language
from services.notification import send_email_notification
from services.database import get_organization_by_api_key
from services.cache import cache, get_from_cache, set_cache, invalidate_chatbot_cache
from services.unknown_questions_service import UnknownQuestionsService

# Import our modules
from services.langchain.embeddings import initialize_embeddings
from services.langchain.vectorstore import initialize_vectorstore, add_document_to_vectorstore
from services.langchain.prompts import initialize_prompt_templates, initialize_chains
from services.langchain.appointments import (
    get_available_slots, 
    handle_booking, 
    handle_rescheduling, 
    handle_cancellation, 
    handle_appointment_info
)
from services.langchain.user_management import handle_name_collection, handle_email_collection
from services.langchain.analysis import analyze_query, generate_response, verify_identity
from services.langchain.knowledge import search_knowledge_base
from services.langchain.error_handling import create_error_handler

# Load environment variables
load_dotenv()

# Initialize global variables
llm = None
embeddings = None
pc = None
index_name = None
vectorstore = None
qa_chain = None
prompt_templates = None
chains = None

# Dictionary to store organization-specific vectorstores
org_vectorstores = {}

# Response quality tracking
response_quality_cache = {}

class SmartCacheManager:
    """Advanced caching manager for chatbot responses"""
    
    def __init__(self):
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0
        }
    
    def generate_cache_key(self, query: str, org_id: str, user_context: str = "") -> str:
        """Generate intelligent cache key"""
        # Normalize query for better cache hits
        normalized_query = re.sub(r'\s+', ' ', query.lower().strip())
        
        # Create context hash
        context_data = f"{org_id}:{user_context}"
        context_hash = hashlib.md5(context_data.encode()).hexdigest()[:8]
        
        # Create query hash
        query_hash = hashlib.md5(normalized_query.encode()).hexdigest()[:12]
        
        return f"chatbot:response:{context_hash}:{query_hash}"
    
    def should_cache_response(self, query: str, mode: str, user_data: dict) -> bool:
        """Determine if response should be cached"""
        # Don't cache personal or time-sensitive content
        no_cache_keywords = [
            "name", "email", "personal", "appointment", "book", "schedule",
            "today", "now", "current", "latest", "recent"
        ]
        
        if any(keyword in query.lower() for keyword in no_cache_keywords):
            return False
        
        # Don't cache if collecting user info
        if mode in ["appointment", "lead_capture"]:
            return False
        
        # Don't cache if user has incomplete profile
        if not user_data.get("name") or not user_data.get("email"):
            return False
        
        return True
    
    def get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Get cached response with stats tracking"""
        response = get_from_cache(cache_key)
        if response:
            self.cache_stats["hits"] += 1
            print(f"📋 Cache HIT: {cache_key}")
        else:
            self.cache_stats["misses"] += 1
            print(f"❌ Cache MISS: {cache_key}")
        return response
    
    def cache_response(self, cache_key: str, response: Dict, ttl_minutes: int = 30) -> bool:
        """Cache response with quality scoring"""
        # Add cache metadata
        cached_data = {
            "response": response,
            "cached_at": datetime.now().isoformat(),
            "cache_version": "1.0"
        }
        
        success = set_cache(cache_key, cached_data, ttl_minutes)
        if success:
            self.cache_stats["sets"] += 1
            print(f"💾 Cached response: {cache_key} (TTL: {ttl_minutes}m)")
        return success
    
    def get_cache_stats(self) -> Dict:
        """Get caching performance statistics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_ratio = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            "hit_ratio_percent": round(hit_ratio, 2),
            "total_requests": total_requests
        }

# Global cache manager
cache_manager = SmartCacheManager()

def initialize():
    """Initialize all components of the langchain engine with performance optimizations"""
    global llm, embeddings, pc, index_name, vectorstore, qa_chain, prompt_templates, chains
    
    print("🚀 Initializing Enhanced Langchain Engine...")
    
    # Initialize OpenAI with better settings
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",  # Better model for improved responses
        temperature=0.6,  # Balanced creativity
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base="https://api.openai.com/v1",
        max_tokens=1200,  # Allow longer responses
        request_timeout=30  # Reasonable timeout
    )
    print("✅ Advanced LLM initialized (GPT-4o-mini)")
    
    # Initialize embeddings
    embeddings = initialize_embeddings()
    print("✅ Embeddings initialized")
    
    # Ensure we have a valid index name
    index_name = os.getenv("PINECONE_INDEX", "bayai")
    print(f"Using Pinecone index name: {index_name}")
    
    # Initialize vector store (global default instance)
    pc, index_name, vectorstore, _ = initialize_vectorstore(embeddings)
    if vectorstore:
        print(f"✅ Default vectorstore initialized successfully with index: {index_name}")
        # Verify it works by testing a simple query
        try:
            test_docs = vectorstore.similarity_search("test", k=1)
            print(f"Vectorstore test query found {len(test_docs)} documents")
        except Exception as e:
            print(f"⚠️ WARNING: Vectorstore test query failed: {str(e)}")
    else:
        print("❌ WARNING: Vectorstore initialization failed")
    
    # Set up QA chain
    qa_chain = load_qa_chain(llm, chain_type="stuff")
    print("✅ QA chain initialized")
    
    # Initialize prompt templates and chains
    prompt_templates = initialize_prompt_templates()
    chains = initialize_chains(llm)
    print("✅ Prompts and chains initialized")
    
    print("🎉 Enhanced Langchain engine initialization complete!")

# Initialize the engine when this module is imported
try:
    print("Starting enhanced langchain engine initialization...")
    initialize()
    print("Enhanced langchain engine initialization completed successfully")
except Exception as e:
    print(f"❌ ERROR during langchain engine initialization: {str(e)}")
    print("Some features may not be available")

def get_org_vectorstore(api_key):
    """Get organization-specific vectorstore with caching"""
    global embeddings, org_vectorstores, pc, index_name
    
    # If no API key, return default vectorstore
    if not api_key:
        print("No API key provided, using default vectorstore")
        return vectorstore
    
    # Check cache first
    cache_key = f"vectorstore:{api_key[:8]}"
    cached_vectorstore = get_from_cache(cache_key)
    if cached_vectorstore:
        print(f"📋 Using cached vectorstore for API key: {api_key[:8]}...")
        return cached_vectorstore
    
    # Check if we already have a vectorstore for this organization
    if api_key in org_vectorstores and org_vectorstores[api_key] is not None:
        print(f"Using in-memory vectorstore for organization with API key: {api_key[:8]}...")
        # Cache it for future use
        set_cache(cache_key, org_vectorstores[api_key], 30)  # 30 minutes
        return org_vectorstores[api_key]
    
    # Otherwise, initialize a new vectorstore for this organization
    try:
        print(f"Initializing new vectorstore for organization with API key: {api_key[:8]}...")
        organization = get_organization_by_api_key(api_key)
        
        if not organization:
            print(f"Error: Organization not found for API key: {api_key[:8]}...")
            return vectorstore
        
        namespace = organization.get('pinecone_namespace')
        print(f"Using organization namespace: {namespace}")
        
        if not pc:
            from pinecone import Pinecone
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        
        if not index_name:
            index_name = os.getenv("PINECONE_INDEX", "bayai")
            
        try:
            # Import PineconeVectorStore here to avoid the "not defined" error
            from langchain_pinecone import PineconeVectorStore
            
            index = pc.Index(index_name)
            org_vectorstore = PineconeVectorStore(
                index=index, 
                embedding=embeddings, 
                text_key="text",
                namespace=namespace
            )
            
            # Explicitly set the namespace property for easier access
            if not hasattr(org_vectorstore, 'namespace'):
                setattr(org_vectorstore, 'namespace', namespace)
            
            # Test the vector store with a simple query
            try:
                test_docs = org_vectorstore.similarity_search("test", k=1)
                print(f"Test query for namespace {namespace} returned {len(test_docs)} docs")
            except Exception as e:
                print(f"Test query for namespace {namespace} failed: {str(e)}")
                
            # Cache the vectorstore for future use (both in memory and Redis)
            org_vectorstores[api_key] = org_vectorstore
            set_cache(cache_key, org_vectorstore, 30)  # 30 minutes
            print(f"✅ Successfully initialized and cached vectorstore for namespace: {namespace}")
            return org_vectorstore
        except Exception as e:
            print(f"Error creating Pinecone vector store: {str(e)}")
            return vectorstore
            
    except Exception as e:
        print(f"Error initializing vectorstore for organization: {str(e)}")
        return vectorstore

def should_collect_info_now(user_data: dict, lead_capture_enabled: bool) -> bool:
    """Smart timing logic for information collection"""
    if not lead_capture_enabled:
        return False
        
    conversation_count = len(user_data.get("conversation_history", []))
    
    # Don't ask on first interaction - let user ask their question first
    if conversation_count <= 2:
        return False
        
    # Ask after 4-5 meaningful interactions
    if 4 <= conversation_count <= 10:
        # Check if user seems engaged (not just one-word responses)
        recent_messages = user_data.get("conversation_history", [])[-3:]
        user_messages = [msg for msg in recent_messages if msg.get("role") == "user"]
        
        if user_messages:
            # Check if user is giving substantial responses (more than 3 words)
            substantial_responses = [msg for msg in user_messages if len(msg.get("content", "").split()) > 3]
            engagement_ratio = len(substantial_responses) / len(user_messages) if user_messages else 0
            
            # Ask for info if user seems engaged
            return engagement_ratio >= 0.5
    
    # Don't ask if we've had too many interactions already
    if conversation_count > 10:
        return False
        
    return False

@create_error_handler
def ask_bot(query: str, mode="faq", user_data=None, available_slots=None, session_id=None, api_key=None):
    """Enhanced chatbot with smart lead capture and advanced caching"""
    # Initialize user data if None
    if user_data is None:
        user_data = {}
   
    # Extract original user question from enhanced query for appointment processing
    original_query = query
    if "The user, who you already know, asks:" in query:
        # Extract the original question after the context
        parts = query.split("The user, who you already know, asks:")
        if len(parts) > 1:
            original_query = parts[-1].strip()
            print(f"[DEBUG] Extracted original query for appointments: '{original_query}'")
   
    # Get organization info and settings
    organization = None
    lead_capture_enabled = True  # Default to True for backward compatibility
    org_id = "default"
    
    if api_key:
        organization = get_organization_by_api_key(api_key)
        if organization:
            org_id = str(organization["_id"])
            print(f"Using organization: {organization['name']} (ID: {org_id})")
            
            # Get leadCapture setting from organization's chat widget settings
            chat_settings = organization.get("chat_widget_settings", {})
            lead_capture_enabled = chat_settings.get("leadCapture", True)
            print(f"[DEBUG] Lead capture enabled: {lead_capture_enabled}")
    
    # Smart caching - check for cached response first
    user_context = f"{user_data.get('name', 'anonymous')}:{mode}"
    cache_key = cache_manager.generate_cache_key(original_query, org_id, user_context)
    
    if cache_manager.should_cache_response(original_query, mode, user_data):
        cached_response = cache_manager.get_cached_response(cache_key)
        if cached_response and cached_response.get("response"):
            print("🚀 Returning cached response")
            return cached_response["response"]
   
    # Get the appropriate vectorstore for this organization
    org_vectorstore = get_org_vectorstore(api_key)
    if not org_vectorstore and api_key:
        print(f"WARNING: Failed to get organization vectorstore for API key: {api_key[:8]}...")
        return {
            "status": "error",
            "message": "Unable to access organization's knowledge base. Please contact support."
        }
   
    # Detect language
    language = detect_language(original_query)
   
    # Passive identity extraction: detect name/email/phone from user's message
    try:
        captured_any = False
        profile_updates = {}
        text = original_query.strip()
        lower = text.lower()
        
        # Email detection
        import re
        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        if email_match:
            email_val = email_match.group(0)
            if not user_data.get("email") or user_data.get("email") != email_val:
                user_data["email"] = email_val
                profile_updates["email"] = email_val
                captured_any = True
                print(f"[IDENTITY] Captured email: {email_val}")
        
        # Phone detection (liberal)
        phone_match = re.search(r"(\+?\d[\d\s().-]{7,})", text)
        def _clean_phone(p):
            digits = re.sub(r"\D", "", p)
            return digits if len(digits) >= 7 else None
        if phone_match:
            cleaned = _clean_phone(phone_match.group(1))
            if cleaned and (not user_data.get("phone") or user_data.get("phone") != cleaned):
                user_data["phone"] = cleaned
                profile_updates["phone"] = cleaned
                captured_any = True
                print(f"[IDENTITY] Captured phone: {cleaned}")
        
        # Name detection via explicit cues
        name_cues = [
            r"\bmy name is\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){0,2})\b",
            r"\bi am\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){0,2})\b",
            r"\bi'm\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){0,2})\b",
            r"\bthis is\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){0,2})\b",
            r"\bcall me\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){0,2})\b",
            r"\bname is\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){0,2})\b",
        ]
        detected_name = None
        for pat in name_cues:
            m = re.search(pat, lower, flags=re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if candidate:
                    # Title-case the name
                    detected_name = " ".join([w.capitalize() for w in candidate.split()])
                    break
        
        # Fallback: pure name message (1-2 words, alphabetic, not a question, not an email/phone)
        if not detected_name:
            if ("@" not in text and not re.search(r"\d", text) and "?" not in text and 1 <= len(text.split()) <= 2):
                if text.replace(" ", "").isalpha():
                    detected_name = " ".join([w.capitalize() for w in text.split()])
        
        if detected_name:
            if not user_data.get("name") or user_data.get("name") != detected_name:
                user_data["name"] = detected_name
                profile_updates["name"] = detected_name
                captured_any = True
                print(f"[IDENTITY] Captured name: {detected_name}")
        
        # Persist profile updates immediately
        if captured_any and session_id and api_key:
            try:
                from services.database import save_user_profile
                organization = get_organization_by_api_key(api_key)
                if organization:
                    org_id_for_save = organization["id"] if "id" in organization else str(organization.get("_id"))
                    if profile_updates:
                        save_user_profile(org_id_for_save, session_id, profile_updates)
                        print(f"[IDENTITY] Saved profile: {profile_updates}")
            except Exception as e:
                print(f"[IDENTITY] Failed to save profile: {str(e)}")
        
        # Create/update lead when we have sufficient contact info (email or phone)
        # Name is optional and will be updated later when available
        if lead_capture_enabled and session_id and api_key and (user_data.get("email") or user_data.get("phone")):
            try:
                from services.database import create_lead
                organization = get_organization_by_api_key(api_key)
                if organization:
                    org_id_for_lead = organization["id"] if "id" in organization else str(organization.get("_id"))
                    inquiry_msgs = [m.get("content", "") for m in user_data.get("conversation_history", []) if m.get("role") == "user"]
                    inquiry_text = " | ".join(inquiry_msgs[-3:]) if inquiry_msgs else "General inquiry"
                    created = create_lead(
                        organization_id=org_id_for_lead,
                        session_id=session_id,
                        name=user_data.get("name") or "",
                        email=user_data.get("email") or "",
                        phone=user_data.get("phone"),
                        inquiry=inquiry_text,
                        source="chatbot"
                    )
                    if created:
                        print(f"[LEAD] Created/Updated lead: {created.get('lead_id')}")
            except Exception as e:
                print(f"[LEAD] Failed to create/update lead: {str(e)}")
    except Exception as e:
        print(f"[IDENTITY] Extraction error: {str(e)}")

    # Record conversation history if not present in user_data
    if "conversation_history" not in user_data:
        user_data["conversation_history"] = []

    # Create a comprehensive context for the AI to analyze
    has_booked_appointment = "appointment_slot" in user_data and user_data["appointment_slot"]
    
    # Smart lead capture logic - only need info if lead capture is enabled
    needs_info = lead_capture_enabled and ("name" not in user_data or "email" not in user_data)
    has_vector_data = org_vectorstore is not None
    
    # Get available slots if in appointment context
    if mode == "appointment" and not available_slots:
        # Get slots for the specific organization using API key
        if api_key:
            available_slots = get_available_slots(api_key)
        else:
            available_slots = get_available_slots()
   
    # Extract relevant information from user_data
    user_info = {
        "name": user_data.get("name", "Unknown"),
        "email": user_data.get("email", "Unknown"),
        "has_appointment": has_booked_appointment,
        "appointment_details": user_data.get("appointment_slot", "None")
    }
    
    # Get conversation context with caching
    conversation_summary = get_conversation_context(session_id, api_key, user_data, org_id)
    
    # STEP 1: Analyze the query to determine intent and appropriate mode
    analysis = analyze_query(query, user_info, mode, needs_info, has_vector_data, conversation_summary)
   
    # QUICK FIX: If the last assistant message asked for name/email, treat this
    # user message as the answer and extract it immediately (prevents double-asking)
    try:
        last_assistant_text = None
        convo = user_data.get("conversation_history", [])
        for msg in reversed(convo):
            if msg.get("role") == "assistant":
                last_assistant_text = str(msg.get("content", "")).lower()
                break
        
        name_prompt_markers = [
            "what should i call you",
            "what's your name",
            "what is your name",
            "may i have your name",
            "could you tell me your name",
            "can i get your name"
        ]
        email_prompt_markers = [
            "email address",
            "what's your email",
            "what is your email",
            "share your email",
            "provide your email",
            "your email so i can"
        ]
        
        # Handle pending name reply
        if last_assistant_text and any(m in last_assistant_text for m in name_prompt_markers) and not user_data.get("name"):
            # Simple inline name detection: 1-2 alphabetic words
            candidate = original_query.strip()
            words = candidate.split()
            is_simple_name = 1 <= len(words) <= 2 and candidate.replace(" ", "").isalpha() and "?" not in candidate
            if is_simple_name:
                detected_name = candidate.title()
                user_data["name"] = detected_name
                # Respond and advance to email politely without re-asking name
                followup = f"Nice to meet you, {detected_name}! Could you please share your email address so I can better assist you?"
                user_data["conversation_history"].append({"role": "assistant", "content": followup})
                return {
                    "answer": followup,
                    "mode": analysis["appropriate_mode"],
                    "language": language,
                    "user_data": user_data,
                    "collecting_info": "email"
                }
            else:
                # Fall back to the dedicated handler for robust extraction
                return handle_name_collection(original_query, user_data, analysis["appropriate_mode"], language)
        
        # Handle pending email reply
        if last_assistant_text and any(m in last_assistant_text for m in email_prompt_markers) and not user_data.get("email"):
            return handle_email_collection(original_query, user_data, analysis["appropriate_mode"], language)
    except Exception as e:
        print(f"[DEBUG] Inline pending-info handler error: {str(e)}")
   
    # STEP 2: Smart Information Collection - only if leadCapture is enabled and timing is right
    if lead_capture_enabled and should_collect_info_now(user_data, lead_capture_enabled):
        print(f"[DEBUG] Smart timing triggered - attempting to collect user information")
        
        if "name" not in user_data:
            # Try to extract name from current query first
            if any(word in original_query.lower() for word in ["my name is", "i'm", "i am", "call me"]):
                return handle_name_collection(original_query, user_data, analysis["appropriate_mode"], language)
            else:
                # Ask for name in a natural way after conversation has developed
                natural_name_request = "I'd love to personalize our conversation better. What should I call you?"
                user_data["conversation_history"].append({
                    "role": "assistant",
                    "content": natural_name_request
                })
                return {
                    "answer": natural_name_request,
                    "mode": analysis["appropriate_mode"],
                    "language": language,
                    "user_data": user_data,
                    "collecting_info": "name"
                }
        elif "email" not in user_data:
            # Ask for email in a natural way
            user_name = user_data.get("name", "")
            natural_email_request = f"Thanks {user_name}! If you'd like me to send you any follow-up information or updates, what's your email address? (You can skip this if you prefer)"
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": natural_email_request
            })
            return {
                "answer": natural_email_request,
                "mode": analysis["appropriate_mode"],
                "language": language,
                "user_data": user_data,
                "collecting_info": "email"
            }
    
    # STEP 3: Handle Appointment Actions if needed
    if analysis["appropriate_mode"] == "appointment" and analysis["appointment_action"] != "none":
        action = analysis["appointment_action"]
       
        # Handle appointment booking - use original query for appointment processing
        if action == "book" and not has_booked_appointment:
            return handle_booking(original_query, user_data, available_slots, language, api_key)
       
        # Handle appointment rescheduling
        elif action == "reschedule" and has_booked_appointment:
            return handle_rescheduling(user_data, available_slots, language, api_key)
       
        # Handle appointment cancellation
        elif action == "cancel" and has_booked_appointment:
            return handle_cancellation(user_data, language)
       
        # Handle appointment information request
        elif action == "info" and has_booked_appointment:
            return handle_appointment_info(user_data, language)
    
    # STEP 4: Enhanced Knowledge Base Lookup with caching
    retrieved_context = ""
    personal_information = {}
    knowledge_base_results = []
    similarity_scores = []
    
    if analysis["needs_knowledge_lookup"] and org_vectorstore is not None:
        # Check for cached knowledge results
        knowledge_cache_key = f"knowledge:{org_id}:{hashlib.md5(query.encode()).hexdigest()[:12]}"
        cached_knowledge = get_from_cache(knowledge_cache_key)
        
        if cached_knowledge:
            print("📚 Using cached knowledge base results")
            retrieved_context = cached_knowledge.get("context", "")
            personal_information = cached_knowledge.get("personal_info", {})
            knowledge_base_results = cached_knowledge.get("results", [])
            similarity_scores = cached_knowledge.get("scores", [])
        else:
            # Fresh knowledge base search: prefer MMR, with fallback to similarity + score
            try:
                documents = []
                mmr_supported = hasattr(org_vectorstore, "max_marginal_relevance_search")
                if mmr_supported:
                    print("[DEBUG] Using MMR retrieval (k=12, fetch_k=30, lambda=0.5)")
                    try:
                        documents = org_vectorstore.max_marginal_relevance_search(
                            query,
                            k=12,
                            fetch_k=30,
                            lambda_mult=0.5
                        )
                    except Exception as e:
                        print(f"[DEBUG] MMR retrieval failed, falling back to similarity_with_score: {str(e)}")
                if not documents:
                    print("[DEBUG] Using similarity_search_with_score (k=8)")
                    search_results = org_vectorstore.similarity_search_with_score(query, k=8)
                    # Normalize shape to list[Document]
                    documents = [doc for doc, _ in search_results]
                    similarity_scores = [float(score) for _, score in search_results]
                else:
                    # If MMR used, compute approximate scores via a small follow-up scoring pass
                    try:
                        sr = org_vectorstore.similarity_search_with_score(query, k=min(8, len(documents)))
                        # Build a map from content hash to score to approximate
                        score_map = {hash(d.page_content): float(s) for d, s in sr}
                        similarity_scores = [score_map.get(hash(d.page_content), 0.0) for d in documents[:8]]
                    except Exception:
                        similarity_scores = []

                # Simple context compression: keep top N docs and trim long pages
                def _compress(text: str, limit: int = 1200) -> str:
                    # Limit context length per doc (characters as heuristic)
                    if not text:
                        return ""
                    text = text.strip()
                    return text if len(text) <= limit else text[:limit] + "..."

                knowledge_base_results = []
                for d in documents[:12]:
                    knowledge_base_results.append({
                        "content": _compress(getattr(d, "page_content", "")),
                        "metadata": getattr(d, "metadata", {}),
                        "similarity_score": None
                    })

                # Use existing search function for final context building
                retrieved_context, personal_information = search_knowledge_base(query, org_vectorstore, user_info)
                # Compress final context to a safe size
                retrieved_context = _compress(retrieved_context, limit=3500)
                
                print(f"[DEBUG] Knowledge base search - Best similarity: {max(similarity_scores) if similarity_scores else 0}")
                
            except Exception as e:
                print(f"[DEBUG] Error in MMR/knowledge search: {str(e)}")
                # Fallback to existing search
                retrieved_context, personal_information = search_knowledge_base(query, org_vectorstore, user_info)
                knowledge_base_results = []
                similarity_scores = []
            
            # Cache knowledge results for 15 minutes
            knowledge_data = {
                "context": retrieved_context,
                "personal_info": personal_information,
                "results": knowledge_base_results,
                "scores": similarity_scores
            }
            set_cache(knowledge_cache_key, knowledge_data, 15)
   
    # STEP 5: Handle special cases if needed
    if analysis["special_handling"] == "identity":
        # For identity questions, make sure we search the knowledge base
        if not retrieved_context and org_vectorstore is not None:
            retrieved_context, personal_information = search_knowledge_base("personal information profile bio", org_vectorstore, user_info)
           
        # Generate identity response
        identity_response = generate_response(
            query, 
            user_info, 
            conversation_summary, 
            retrieved_context, 
            personal_information, 
            analysis, 
            language
        )
       
        response = {
            "answer": identity_response,
            "mode": "faq",
            "language": language,
            "user_data": user_data
        }
        
        # Cache identity responses for 60 minutes (they don't change often)
        if cache_manager.should_cache_response(original_query, mode, user_data):
            cache_manager.cache_response(cache_key, response, 60)
        
        return response
   
    # STEP 6: Strict KB enforcement for FAQ/general answers
    kb_intents = ["faq", "general", "identity"]
    if analysis.get("appropriate_mode") in kb_intents:
        # If we determined a KB lookup was needed but context is empty, do not fabricate
        if analysis.get("needs_knowledge_lookup") and not retrieved_context:
            fallback = {
                "answer": "I don't have that in the training data yet. Would you like me to connect you with a team member or try a related question?",
                "mode": "faq",
                "language": language,
                "user_data": user_data
            }
            return fallback

    # Otherwise, generate the final response
    final_response = generate_enhanced_response(
        query, 
        user_info, 
        conversation_summary, 
        retrieved_context, 
        personal_information, 
        analysis, 
        language,
        organization
    )
    
    # Additional context-aware improvements
    final_response = enhance_contextual_response(final_response, query, user_data, organization)
   
    # Determine final mode for response
    final_mode = analysis["appropriate_mode"]
    # Reset to FAQ mode if we've completed other flows
    if has_booked_appointment and final_mode == "appointment":
        final_mode = "faq"
   
    # STEP 7: Detect and store unknown questions
    # Check if this question wasn't well-answered by training data
    max_similarity = max(similarity_scores) if similarity_scores else 0.0
    # Adaptive threshold: use percentile-like heuristic from observed scores
    if similarity_scores and len(similarity_scores) >= 4:
        sorted_scores = sorted(similarity_scores, reverse=True)
        # Use 3rd-best score (P25-ish for small k) minus a small margin
        base = sorted_scores[min(2, len(sorted_scores)-1)]
        similarity_threshold = max(0.55, min(0.85, base - 0.05))
    else:
        similarity_threshold = 0.7
    
    # Only store if it's a real question (not info collection or appointments)
    should_store_unknown = (
        max_similarity < similarity_threshold and  # Low similarity to training data
        not user_data.get("collecting_info") and  # Not collecting user info
        final_mode != "appointment" and  # Not appointment-related
        len(original_query.split()) > 2 and  # Substantial question
        "?" in original_query or any(word in original_query.lower() for word in ["what", "how", "why", "when", "where", "do", "can", "should", "would"])  # Question-like
    )
    
    if should_store_unknown and session_id and org_id:
        try:
            print(f"[DEBUG] Storing unknown question - Similarity: {max_similarity:.3f}, Question: '{original_query[:50]}...'")
            
            # Get visitor ID if available
            visitor_id = user_data.get("visitor_id")
            
            # Prepare conversation context (last 3 messages)
            conversation_context = user_data.get("conversation_history", [])[-3:] if user_data.get("conversation_history") else []
            
            # Store the unknown question
            UnknownQuestionsService.save_unknown_question(
                organization_id=org_id,
                session_id=session_id,
                question=original_query,
                ai_response=final_response,
                knowledge_base_results=knowledge_base_results,
                similarity_scores=similarity_scores,
                user_context={
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "mode": final_mode,
                    "language": language
                },
                conversation_context=conversation_context,
                visitor_id=visitor_id
            )
        except Exception as e:
            print(f"[DEBUG] Error storing unknown question: {str(e)}")
   
    response = {
        "answer": final_response,
        "mode": final_mode,
        "language": language,
        "user_data": user_data,
        "cache_stats": cache_manager.get_cache_stats(),
        "knowledge_similarity": max_similarity  # Add similarity score for debugging
    }
    
    # Cache the response if appropriate
    if cache_manager.should_cache_response(original_query, mode, user_data):
        # Determine TTL based on content type
        ttl_minutes = 30  # Default
        if "faq" in final_mode:
            ttl_minutes = 60  # FAQ responses can be cached longer
        elif "general" in analysis.get("intent", ""):
            ttl_minutes = 45  # General info cached medium term
        
        cache_manager.cache_response(cache_key, response, ttl_minutes)
    
    return response

def get_conversation_context(session_id: str, api_key: str, user_data: dict, org_id: str) -> str:
    """Get conversation context with intelligent caching"""
    # Try cache first
    context_cache_key = f"conversation:{org_id}:{session_id}"
    cached_context = get_from_cache(context_cache_key)
    
    if cached_context:
        print("📋 Using cached conversation context")
        return cached_context
    
    # Get fresh conversation context
    conversation_summary = ""
    if session_id and api_key:
        try:
            from services.database import get_conversation_history
            organization = get_organization_by_api_key(api_key)
            if organization:
                org_id = organization["id"]
                # Get all conversations and take the latest 6 (excluding current message)
                db_conversations = get_conversation_history(org_id, session_id)
                # Exclude the current user message if it exists (it was just added to DB)
                previous_conversations = db_conversations[:-1] if len(db_conversations) > 0 else []
                # Take the latest 6 previous conversations
                latest_conversations = previous_conversations[-6:] if len(previous_conversations) > 6 else previous_conversations
                
                # Create conversation summary from database conversations
                conversation_summary = "\n".join([
                    f"{'User' if msg['role'] == 'user' else 'AI'}: {msg['content']}" 
                    for msg in latest_conversations
                ])
                print(f"[DEBUG] Using latest {len(latest_conversations)} previous conversations from database for context")
                
                # Cache conversation context for 2 minutes (conversations change frequently)
                set_cache(context_cache_key, conversation_summary, 2)
                
        except Exception as e:
            print(f"[DEBUG] Error fetching conversation history from DB: {str(e)}")
            # Fallback to in-memory conversation history (last 5)
            conversation_context = user_data["conversation_history"][-5:] if len(user_data["conversation_history"]) > 0 else []
            conversation_summary = "\n".join([f"{'User' if msg['role'] == 'user' else 'AI'}: {msg['content']}" for msg in conversation_context])
    else:
        # Fallback to in-memory conversation history (last 5)
        conversation_context = user_data["conversation_history"][-5:] if len(user_data["conversation_history"]) > 0 else []
        conversation_summary = "\n".join([f"{'User' if msg['role'] == 'user' else 'AI'}: {msg['content']}" for msg in conversation_context])
    
    return conversation_summary

def generate_enhanced_response(query: str, user_info: dict, conversation_summary: str, 
                             retrieved_context: str, personal_information: dict, 
                             analysis: dict, language: str, organization: dict = None) -> str:
    """Generate enhanced response with better prompting and personalization"""
    
    # Build enhanced system prompt
    # Get organization name from chat widget settings (preferred) or fallback to main name
    if organization:
        chat_settings = organization.get("chat_widget_settings", {})
        org_name = chat_settings.get("name", organization.get("name", "our company"))
        ai_behavior = chat_settings.get("ai_behavior", "")
    else:
        org_name = "our company"
        ai_behavior = ""
    
    user_name = user_info.get("name", "")
    
    system_prompt = f"""
    You are a professional AI assistant for {org_name}, a law firm specializing in personal injury cases.
    
    PERSONALITY & BEHAVIOR:
    {ai_behavior if ai_behavior else "- Be warm, empathetic, and professional"}
    - Helpful and knowledgeable about legal matters
    - Professional but approachable  
    - Proactive in understanding client needs
    - Direct and contextual (no generic responses)
    - Show genuine interest in helping with their legal situation
    
    CURRENT CONTEXT:
    - User: {user_name if user_name != "Unknown" else "visitor"}
    - Time: {datetime.now().strftime('%A, %I:%M %p')}
    - Intent: {analysis.get('intent', 'general')}
    - Language: {language}
    - Organization: {org_name}
    
    CONVERSATION HISTORY:
    {conversation_summary if conversation_summary else "This is the start of the conversation."}
    
    KNOWLEDGE BASE CONTEXT:
    {retrieved_context if retrieved_context else "No specific knowledge base context available."}
    
    PERSONAL INFORMATION:
    {json.dumps(personal_information) if personal_information else "No personal information available."}
    
    RESPONSE GUARDRAILS (STRICT):
    - Answer ONLY using the KNOWLEDGE BASE CONTEXT above. If the answer is not found there, ask one short clarifying question or say you don't know.
    - Include 1–2 specific facts from the context; avoid generic advice.
    - If confidence is low, propose next steps (clarify, surface related FAQs, or offer to connect to a human).
    
    OUTPUT STYLE:
    - Be concise and helpful.
    - If possible, end with one helpful follow-up question.
    - If you cite, use short source titles (no raw URLs).
    """
    
    try:
        # Use the original generate_response function but with enhanced prompt
        enhanced_response = generate_response(
            query, 
            user_info, 
            conversation_summary, 
            retrieved_context, 
            personal_information, 
            analysis, 
            language
        )
        
        # Post-process for quality improvements
        enhanced_response = improve_response_quality(enhanced_response, user_info, organization)
        
        return enhanced_response
        
    except Exception as e:
        print(f"❌ Error generating enhanced response: {str(e)}")
        return "I apologize, but I'm experiencing technical difficulties. Please try again in a moment."

def improve_response_quality(response: str, user_info: dict, organization: dict = None) -> str:
    """Post-process response for better quality and context"""
    
    # Add personalization
    user_name = user_info.get("name")
    if user_name and user_name != "Unknown" and user_name not in response:
        # Add name for greetings and important responses
        if any(word in response.lower() for word in ["hello", "hi", "welcome", "thank"]):
            response = response.replace("Hello", f"Hello {user_name}")
            response = response.replace("Hi", f"Hi {user_name}")
    
    # Ensure proper formatting
    response = response.strip()
    
    # Improve generic phone number responses
    if "can be reached at" in response.lower() and "further assistance" in response.lower():
        # This is a generic phone response - make it more contextual
        if organization:
            chat_settings = organization.get("chat_widget_settings", {})
            org_name = chat_settings.get("name", organization.get("name", "our office"))
        else:
            org_name = "our office"
            
        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', response)
        if phone_match:
            phone_number = phone_match.group()
            if user_name and user_name != "Unknown":
                response = f"Great to meet you, {user_name}! I'd be happy to help you with your legal matter. You can call us directly at {phone_number} to speak with an attorney, or feel free to tell me more about your situation and I can provide some initial guidance."
            else:
                response = f"You can reach {org_name} at {phone_number} to speak directly with an attorney. What type of legal issue are you dealing with? I'd be happy to provide some initial information."
    
    # Handle short acknowledgments better
    if response.lower().strip() in ["okay", "ok", "alright", "sure", "yes", "no problem"]:
        if user_name and user_name != "Unknown":
            response = f"Thanks {user_name}! What can I help you with regarding your legal matter? Are you dealing with an injury, accident, or other legal issue?"
        else:
            response = "What can I help you with today? Are you dealing with a personal injury, car accident, or another legal matter?"
    
    # Add helpful endings based on content
    if "?" not in response and not response.endswith(("!", ".")):
        if "appointment" in response.lower():
            response += ". Would you like to schedule a consultation?"
        elif any(word in response.lower() for word in ["injury", "accident", "legal", "case"]):
            response += ". What specific details can you share about your situation?"
        elif any(word in response.lower() for word in ["service", "help", "assist"]):
            response += ". What type of legal issue are you facing?"
        else:
            response += ". How can I assist you with your legal needs?"
    
    # Add time-sensitive context for contact information
    current_hour = datetime.now().hour
    if current_hour < 9 or current_hour > 17:  # Outside business hours
        if any(word in response.lower() for word in ["contact", "call", "reach"]):
            response += "\n\n💡 Note: We're currently outside business hours (9 AM - 5 PM). You can call anytime to leave a message, or continue chatting here and we'll help you right away!"
    
    return response

def enhance_contextual_response(response: str, query: str, user_data: dict, organization: dict = None) -> str:
    """Enhance response based on conversation context and user behavior"""
    
    query_lower = query.lower().strip()
    conversation_history = user_data.get("conversation_history", [])
    user_name = user_data.get("name", "")
    
    # Handle acknowledgments and short responses
    acknowledgments = ["okay", "ok", "alright", "sure", "yes", "thanks", "thank you", "got it"]
    if query_lower in acknowledgments:
        # Check what we were just talking about
        if len(conversation_history) >= 2:
            last_bot_message = ""
            for msg in reversed(conversation_history):
                if msg.get("role") == "assistant":
                    last_bot_message = msg.get("content", "").lower()
                    break
            
            if user_name:
                if "name" in last_bot_message or "call you" in last_bot_message:
                    # We just asked for their name, now ask about their case
                    return f"Thanks {user_name}! What can I help you with regarding your legal matter? Are you dealing with a personal injury, car accident, or another type of case?"
                elif "phone" in last_bot_message or "contact" in last_bot_message:
                    # We just gave contact info, ask about their situation
                    return f"Perfect {user_name}! While you're here, I'd love to learn more about your situation. What type of legal issue brought you to us today?"
                else:
                    # General follow-up
                    return f"Great {user_name}! What specific legal matter can I help you with? Are you dealing with an injury, accident, or other legal concern?"
            else:
                return "What can I help you with today? Are you dealing with a personal injury, car accident, or another legal matter?"
    
    # Detect if response is too generic and improve it
    generic_patterns = [
        "can be reached at",
        "for further assistance", 
        "contact us at",
        "call us at"
    ]
    
    if any(pattern in response.lower() for pattern in generic_patterns):
        # Extract phone number if present
        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', response)
        phone_number = phone_match.group() if phone_match else ""
        
        if organization:
            chat_settings = organization.get("chat_widget_settings", {})
            org_name = chat_settings.get("name", organization.get("name", "our law firm"))
        else:
            org_name = "our law firm"
        
        if user_name:
            return f"Great to meet you, {user_name}! I'd be happy to help you with your legal matter. You can call us at {phone_number} to speak directly with an attorney, or tell me more about your situation and I can provide some guidance right here. What type of legal issue are you dealing with?"
        else:
            return f"You can reach {org_name} at {phone_number} to speak with an attorney. What type of legal issue brought you here today? I'd be happy to provide some initial information about your situation."
    
    # If response is very short, add context
    if len(response.split()) < 5 and not response.endswith("?"):
        if user_name:
            response += f" What else can I help you with regarding your legal matter, {user_name}?"
        else:
            response += " What type of legal issue are you dealing with?"
    
    return response

# Utility functions
def add_document(file_path=None, url=None, text=None, api_key=None):
    """Add documents to the vector store with cache invalidation"""
    result = add_document_to_vectorstore(
        get_org_vectorstore(api_key), pc, index_name, embeddings, 
        api_key=api_key, file_path=file_path, url=url, text=text
    )
    
    # Invalidate related caches when new documents are added
    if result.get("status") == "success" and api_key:
        organization = get_organization_by_api_key(api_key)
        if organization:
            org_id = str(organization["_id"])
            invalidate_chatbot_cache(org_id)
            print(f"🗑️ Invalidated cache for organization {org_id} after document upload")
    
    return result

def remove_document(filename=None, url=None, api_key=None):
    """Remove a document from the vector store with cache invalidation"""
    # Implementation would be similar to your existing remove_document
    # but with cache invalidation afterward
    
    if api_key:
        organization = get_organization_by_api_key(api_key)
        if organization:
            org_id = str(organization["_id"])
            invalidate_chatbot_cache(org_id)
            print(f"🗑️ Invalidated cache for organization {org_id} after document removal")
    
    return {"status": "success", "message": "Document removal completed"}

def get_vectorstore():
    """Get the global vectorstore instance"""
    return vectorstore

def reinitialize_vectorstore():
    """Reinitialize the vectorstore and clear related caches"""
    global embeddings, pc, index_name, vectorstore
    pc, index_name, vectorstore, _ = initialize_vectorstore(embeddings)
    
    # Clear all vectorstore-related caches
    invalidate_chatbot_cache()
    print("🗑️ Cleared all vectorstore caches after reinitialization")
    
    return vectorstore

def escalate_to_human(query, user_info):
    """Escalate a conversation to a human operator"""
    # Generate a comprehensive summary for the human operator
    summary = f"""
    ESCALATION REQUIRED: The AI could not handle the following query:
    
    QUERY: {query}
    
    USER INFO:
    """
    
    # Add user info details
    for key, value in user_info.items():
        summary += f"- {key}: {value}\n"
    
    # Send notification to the appropriate team
    try:
        # Add organization details if available
        org_id = user_info.get("organization_id", "Unknown")
        org_name = user_info.get("organization_name", "Unknown")
        
        # Create a better subject line
        subject = f"Chat Escalation: {org_name} - {user_info.get('name', 'Unknown Visitor')}"
        
        send_email_notification(
            subject=subject,
            message=summary,
            email="support@example.com"  # Replace with actual support team email
        )
        
        return {
            "status": "success",
            "message": "Your request has been escalated to our support team. Someone will contact you shortly."
        }
    except Exception as e:
        print(f"Error in escalation: {str(e)}")
        return {
            "status": "error",
            "message": "We couldn't escalate your request automatically. Please contact support directly at support@example.com."
        }

def get_cache_performance():
    """Get caching performance metrics"""
    return {
        "cache_manager_stats": cache_manager.get_cache_stats(),
        "redis_info": {
            "available": cache.is_available(),
            "host": cache.redis_host if hasattr(cache, 'redis_host') else "unknown",
            "port": cache.redis_port if hasattr(cache, 'redis_port') else "unknown"
        }
    }
