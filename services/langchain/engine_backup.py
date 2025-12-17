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
    
    if analysis["needs_knowledge_lookup"] and org_vectorstore is not None:
        # Check for cached knowledge results
        knowledge_cache_key = f"knowledge:{org_id}:{hashlib.md5(query.encode()).hexdigest()[:12]}"
        cached_knowledge = get_from_cache(knowledge_cache_key)
        
        if cached_knowledge:
            print("📚 Using cached knowledge base results")
            retrieved_context = cached_knowledge.get("context", "")
            personal_information = cached_knowledge.get("personal_info", {})
        else:
            # Fresh knowledge base search
            retrieved_context, personal_information = search_knowledge_base(query, org_vectorstore, user_info)
            
            # Cache knowledge results for 15 minutes
            knowledge_data = {
                "context": retrieved_context,
                "personal_info": personal_information
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
   
    # STEP 6: Generate the final response with quality improvements
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
   
    # Determine final mode for response
    final_mode = analysis["appropriate_mode"]
    # Reset to FAQ mode if we've completed other flows
    if has_booked_appointment and final_mode == "appointment":
        final_mode = "faq"
   
    response = {
        "answer": final_response,
        "mode": final_mode,
        "language": language,
        "user_data": user_data,
        "cache_stats": cache_manager.get_cache_stats()
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
    org_name = organization.get("name", "our company") if organization else "our company"
    user_name = user_info.get("name", "")
    
    system_prompt = f"""
    You are a professional AI assistant for {org_name}.
    
    PERSONALITY:
    - Warm, helpful, and knowledgeable
    - Professional but approachable  
    - Proactive in offering solutions
    - Empathetic to user concerns
    
    CURRENT CONTEXT:
    - User: {user_name if user_name != "Unknown" else "visitor"}
    - Time: {datetime.now().strftime('%A, %I:%M %p')}
    - Intent: {analysis.get('intent', 'general')}
    - Language: {language}
    
    CONVERSATION HISTORY:
    {conversation_summary if conversation_summary else "This is the start of the conversation."}
    
    KNOWLEDGE BASE CONTEXT:
    {retrieved_context if retrieved_context else "No specific knowledge base context available."}
    
    PERSONAL INFORMATION:
    {json.dumps(personal_information) if personal_information else "No personal information available."}
    
    RESPONSE GUIDELINES:
    - Address the user by name when appropriate
    - Provide specific, actionable answers
    - Reference previous conversation if relevant
    - Use the knowledge base information to give accurate responses
    - Keep responses natural and conversational
    - End with a helpful next step or question when appropriate
    - If you don't know something, say so and offer to find out
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
    """Post-process response for better quality"""
    
    # Add personalization
    user_name = user_info.get("name")
    if user_name and user_name != "Unknown" and user_name not in response:
        # Add name for greetings and important responses
        if any(word in response.lower() for word in ["hello", "hi", "welcome", "thank"]):
            response = response.replace("Hello", f"Hello {user_name}")
            response = response.replace("Hi", f"Hi {user_name}")
    
    # Ensure proper formatting
    response = response.strip()
    
    # Add helpful endings based on content
    if "?" not in response and not response.endswith(("!", ".")):
        if "appointment" in response.lower():
            response += ". Would you like to schedule an appointment?"
        elif any(word in response.lower() for word in ["service", "help", "assist"]):
            response += ". How else can I help you today?"
        else:
            response += ". Is there anything else you'd like to know?"
    
    # Add time-sensitive context
    current_hour = datetime.now().hour
    if current_hour < 9 or current_hour > 17:  # Outside business hours
        if any(word in response.lower() for word in ["contact", "call", "reach"]):
            response += "\n\n💡 Please note: We're currently outside business hours (9 AM - 5 PM). We'll respond to your inquiry first thing in the morning!"
    
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

def escalate_to_human(query: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple escalation function that returns a message indicating human assistance is needed.
    """
    return {
        "answer": "Your request has been escalated to our support team. A human agent will assist you shortly.",
        "escalated": True,
        "context": context
    }
