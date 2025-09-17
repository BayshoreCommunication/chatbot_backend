from langchain_openai import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage, AIMessage
from dotenv import load_dotenv
import os
import openai
import re
import json
from datetime import datetime, timedelta
import hashlib

from services.language_detect import detect_language
from services.notification import send_email_notification
from services.database import get_organization_by_api_key
from services.cache import get_from_cache, set_cache

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

class ImprovedChatbotEngine:
    """Enhanced chatbot engine with better response quality and performance"""
    
    def __init__(self):
        self.llm = None
        self.embeddings = None
        self.vectorstore = None
        self.org_vectorstores = {}
        self.response_cache = {}
        self.conversation_memories = {}  # Per-session memory
        self.personality_prompt = self._load_personality()
        
    def _load_personality(self):
        """Load chatbot personality and behavior guidelines"""
        return """
        You are a professional, friendly, and knowledgeable AI assistant. 
        
        PERSONALITY TRAITS:
        - Warm and approachable, but professional
        - Confident in your expertise
        - Patient with complex questions
        - Proactive in offering help
        - Empathetic to user concerns
        
        RESPONSE STYLE:
        - Use natural, conversational language
        - Provide specific, actionable answers
        - Ask clarifying questions when needed
        - Acknowledge user emotions
        - End with helpful next steps
        
        QUALITY STANDARDS:
        - Always be accurate and truthful
        - If unsure, say so and offer to find out
        - Provide context for your recommendations
        - Use examples when helpful
        - Keep responses concise but complete
        """
    
    def initialize(self):
        """Initialize enhanced chatbot components"""
        print("🚀 Initializing Enhanced Chatbot Engine...")
        
        # Initialize with GPT-4 for better responses
        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",  # Better than 3.5-turbo, cost-effective
            temperature=0.7,  # More creative responses
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=1000,  # Longer responses when needed
            streaming=True   # Enable streaming for faster perceived response
        )
        print("✅ Advanced LLM initialized (GPT-4o-mini)")
        
        # Initialize embeddings
        self.embeddings = initialize_embeddings()
        print("✅ Embeddings initialized")
        
        # Initialize vectorstore
        from services.langchain.vectorstore import initialize_vectorstore
        pc, index_name, self.vectorstore, _ = initialize_vectorstore(self.embeddings)
        print("✅ Vector store initialized")
        
        print("🎉 Enhanced Chatbot Engine ready!")
    
    def _get_cache_key(self, query: str, user_context: str) -> str:
        """Generate cache key for response caching"""
        combined = f"{query}_{user_context}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _get_conversation_memory(self, session_id: str):
        """Get or create conversation memory for session"""
        if session_id not in self.conversation_memories:
            self.conversation_memories[session_id] = ConversationBufferWindowMemory(
                k=10,  # Remember last 10 exchanges
                return_messages=True
            )
        return self.conversation_memories[session_id]
    
    def _determine_temperature(self, query_type: str) -> float:
        """Adaptive temperature based on query type"""
        temperature_map = {
            "factual": 0.1,      # Low creativity for facts
            "appointment": 0.3,   # Structured responses
            "creative": 0.8,      # High creativity
            "problem_solving": 0.6, # Balanced approach
            "casual": 0.7         # Natural conversation
        }
        return temperature_map.get(query_type, 0.5)
    
    def _enhance_context(self, query: str, user_data: dict, session_id: str) -> dict:
        """Create rich context for better responses"""
        
        # Get conversation memory
        memory = self._get_conversation_memory(session_id)
        
        # Build user profile
        user_profile = {
            "name": user_data.get("name", "Unknown"),
            "email": user_data.get("email", "Unknown"),
            "returning_user": user_data.get("returning_user", False),
            "appointment_history": user_data.get("appointment_history", []),
            "preferences": user_data.get("preferences", {}),
            "interaction_count": len(user_data.get("conversation_history", [])),
        }
        
        # Detect query intent and type
        intent_analysis = self._analyze_intent(query)
        
        # Time context
        time_context = {
            "current_time": datetime.now().isoformat(),
            "day_of_week": datetime.now().strftime("%A"),
            "is_business_hours": self._is_business_hours()
        }
        
        return {
            "user_profile": user_profile,
            "intent_analysis": intent_analysis,
            "time_context": time_context,
            "memory": memory,
            "session_id": session_id
        }
    
    def _analyze_intent(self, query: str) -> dict:
        """Advanced intent analysis"""
        query_lower = query.lower()
        
        # Intent patterns
        intents = {
            "greeting": ["hello", "hi", "hey", "good morning", "good afternoon"],
            "question": ["what", "how", "why", "when", "where", "who", "?"],
            "request": ["can you", "could you", "please", "i need", "help me"],
            "complaint": ["problem", "issue", "wrong", "error", "not working"],
            "compliment": ["thank you", "thanks", "great", "excellent", "amazing"],
            "appointment": ["book", "schedule", "appointment", "meeting", "slot"],
            "information": ["tell me about", "explain", "describe", "information"]
        }
        
        detected_intents = []
        for intent, patterns in intents.items():
            if any(pattern in query_lower for pattern in patterns):
                detected_intents.append(intent)
        
        # Determine primary intent
        primary_intent = detected_intents[0] if detected_intents else "general"
        
        # Determine emotional tone
        emotional_indicators = {
            "positive": ["happy", "excited", "great", "love", "amazing"],
            "negative": ["frustrated", "angry", "upset", "disappointed", "terrible"],
            "urgent": ["urgent", "asap", "immediately", "emergency", "quickly"],
            "confused": ["confused", "don't understand", "unclear", "help"]
        }
        
        emotional_tone = "neutral"
        for tone, indicators in emotional_indicators.items():
            if any(indicator in query_lower for indicator in indicators):
                emotional_tone = tone
                break
        
        return {
            "primary_intent": primary_intent,
            "all_intents": detected_intents,
            "emotional_tone": emotional_tone,
            "query_type": self._classify_query_type(query),
            "complexity": "high" if len(query.split()) > 20 else "medium" if len(query.split()) > 10 else "simple"
        }
    
    def _classify_query_type(self, query: str) -> str:
        """Classify query type for temperature adjustment"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["what is", "define", "explain", "how many"]):
            return "factual"
        elif any(word in query_lower for word in ["book", "schedule", "appointment"]):
            return "appointment"
        elif any(word in query_lower for word in ["create", "write", "suggest", "recommend"]):
            return "creative"
        elif any(word in query_lower for word in ["problem", "issue", "fix", "solve"]):
            return "problem_solving"
        else:
            return "casual"
    
    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        now = datetime.now()
        return 9 <= now.hour <= 17 and now.weekday() < 5  # 9 AM - 5 PM, Mon-Fri
    
    @create_error_handler
    def ask_bot_enhanced(self, query: str, mode="faq", user_data=None, 
                        available_slots=None, session_id=None, api_key=None):
        """Enhanced bot processing with better context and responses"""
        
        if user_data is None:
            user_data = {}
        
        # Check cache first for common queries
        cache_key = self._get_cache_key(query, str(user_data.get("name", "")))
        cached_response = get_from_cache(cache_key)
        if cached_response and not mode == "appointment":  # Don't cache appointments
            print("📋 Returning cached response")
            return cached_response
        
        # Build enhanced context
        context = self._enhance_context(query, user_data, session_id or "default")
        
        # Adjust LLM temperature based on query type
        query_type = context["intent_analysis"]["query_type"]
        self.llm.temperature = self._determine_temperature(query_type)
        
        # Get organization-specific vectorstore
        org_vectorstore = self._get_org_vectorstore(api_key)
        
        # Enhanced knowledge retrieval
        knowledge_context = ""
        if org_vectorstore:
            try:
                # Use semantic search with multiple strategies
                search_results = org_vectorstore.similarity_search(
                    query, 
                    k=5,  # Get more results
                    score_threshold=0.7  # Only high-quality matches
                )
                
                if search_results:
                    knowledge_context = "\n".join([doc.page_content for doc in search_results])
                    print(f"📚 Retrieved {len(search_results)} knowledge base documents")
                
            except Exception as e:
                print(f"⚠️ Knowledge retrieval error: {str(e)}")
        
        # Generate enhanced response
        response = self._generate_enhanced_response(
            query, context, knowledge_context, mode, user_data
        )
        
        # Cache the response (except appointments and personal info)
        if mode != "appointment" and not any(keyword in query.lower() 
                                           for keyword in ["name", "email", "personal"]):
            set_cache(cache_key, response, expiry_minutes=60)
        
        # Update conversation memory
        memory = context["memory"]
        memory.chat_memory.add_user_message(query)
        memory.chat_memory.add_ai_message(response["answer"])
        
        return response
    
    def _generate_enhanced_response(self, query: str, context: dict, 
                                  knowledge_context: str, mode: str, user_data: dict) -> dict:
        """Generate enhanced response with personality and context"""
        
        user_profile = context["user_profile"]
        intent = context["intent_analysis"]
        time_context = context["time_context"]
        
        # Build comprehensive prompt
        system_prompt = f"""
        {self.personality_prompt}
        
        CURRENT CONTEXT:
        - User: {user_profile['name']} ({'returning' if user_profile['returning_user'] else 'new'} user)
        - Time: {time_context['day_of_week']}, {'business hours' if time_context['is_business_hours'] else 'after hours'}
        - Intent: {intent['primary_intent']} (tone: {intent['emotional_tone']})
        - Query complexity: {intent['complexity']}
        - Mode: {mode}
        
        KNOWLEDGE BASE:
        {knowledge_context if knowledge_context else "No specific knowledge base context available"}
        
        INSTRUCTIONS:
        - Address the user by name when appropriate
        - Match the emotional tone of the query
        - Provide specific, actionable information
        - If after hours, mention response time expectations
        - Use the knowledge base information to provide accurate answers
        - Keep responses natural and conversational
        - End with a helpful next step or question
        """
        
        # Generate response using enhanced prompt
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            response = openai.chat.completions.create(
                model=self.llm.model_name,
                messages=messages,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens
            )
            
            answer = response.choices[0].message.content
            
            # Post-process response
            answer = self._post_process_response(answer, context)
            
            return {
                "answer": answer,
                "mode": mode,
                "language": detect_language(query),
                "user_data": user_data,
                "confidence": self._calculate_confidence(knowledge_context, intent),
                "response_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Response generation error: {str(e)}")
            return {
                "answer": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
                "mode": mode,
                "language": "en",
                "user_data": user_data
            }
    
    def _post_process_response(self, answer: str, context: dict) -> str:
        """Post-process response for quality improvements"""
        
        # Add personalization
        user_name = context["user_profile"]["name"]
        if user_name != "Unknown" and user_name not in answer:
            # Sometimes add name for warmth (not every response)
            if context["intent_analysis"]["primary_intent"] in ["greeting", "compliment"]:
                answer = answer.replace("Hello!", f"Hello {user_name}!")
        
        # Add time-appropriate responses
        if not context["time_context"]["is_business_hours"]:
            if "contact" in answer.lower() or "call" in answer.lower():
                answer += "\n\nPlease note: We're currently outside business hours. We'll respond to your inquiry first thing in the morning!"
        
        # Ensure proper formatting
        answer = answer.strip()
        
        # Add helpful endings for certain intents
        if context["intent_analysis"]["primary_intent"] == "question" and not answer.endswith("?"):
            answer += "\n\nIs there anything else you'd like to know about this?"
        
        return answer
    
    def _calculate_confidence(self, knowledge_context: str, intent: dict) -> float:
        """Calculate response confidence score"""
        confidence = 0.5  # Base confidence
        
        # Boost confidence if we have knowledge base context
        if knowledge_context:
            confidence += 0.3
        
        # Adjust based on intent clarity
        if intent["primary_intent"] != "general":
            confidence += 0.1
        
        # Reduce confidence for complex queries without context
        if intent["complexity"] == "high" and not knowledge_context:
            confidence -= 0.2
        
        return min(1.0, max(0.1, confidence))
    
    def _get_org_vectorstore(self, api_key):
        """Get organization vectorstore (simplified for this example)"""
        # This would use your existing get_org_vectorstore logic
        return self.vectorstore

# Global instance
enhanced_engine = ImprovedChatbotEngine()

def initialize_enhanced():
    """Initialize the enhanced engine"""
    enhanced_engine.initialize()

def ask_bot_enhanced(query: str, mode="faq", user_data=None, 
                    available_slots=None, session_id=None, api_key=None):
    """Enhanced ask_bot function"""
    return enhanced_engine.ask_bot_enhanced(
        query, mode, user_data, available_slots, session_id, api_key
    )
