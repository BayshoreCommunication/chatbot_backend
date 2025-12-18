import os
import time
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI

# LangChain & Pinecone Imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pinecone import Pinecone

# Initialize OpenAI client for web search
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Setup
load_dotenv()

# --- 1. Global Memory (Replace with Redis/Database in production) ---
CHAT_HISTORY_DB = {} 

def get_session_history(session_id: str) -> List:
    """Retrieves chat history for a specific user session."""
    return CHAT_HISTORY_DB.get(session_id, [])

def save_to_history(session_id: str, user_query: str, ai_response: str):
    """Saves the latest turn to memory."""
    if session_id not in CHAT_HISTORY_DB:
        CHAT_HISTORY_DB[session_id] = []
    
    # Keep last 10 turns
    history = CHAT_HISTORY_DB[session_id]
    history.append(HumanMessage(content=user_query))
    history.append(AIMessage(content=ai_response))
    CHAT_HISTORY_DB[session_id] = history[-10:] 

# Initialize Singletons
try:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1024)
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX", "bayai")
    
    # Using GPT-4o-mini for speed and intelligence
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.4,  # Balanced creativity for natural conversation
        max_tokens=600
    )
except Exception as e:
    raise e

def search_web_for_info(query: str, company_name: str) -> Optional[str]:
    """TIER 2: Search web for information not in knowledge base"""
    try:
        print(f"\n[TIER 2: WEB SEARCH]")
        print(f"[WEB SEARCH] 🔍 Query: {query}")
        print(f"[WEB SEARCH] 🏢 Company: {company_name}")
        
        prompt = f"""Search the web and find the answer to this question about {company_name}:

Question: {query}

Provide a concise, factual answer if found. If not found, say "Information not available online."
Focus on: contact info, services, pricing, hours, location, team, credentials."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant with web search capabilities. Provide factual, accurate answers only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        
        result = response.choices[0].message.content
        
        # Check if actually found information
        if result and "not available" not in result.lower() and "cannot find" not in result.lower():
            print(f"[WEB SEARCH] ✅ SUCCESS: Found relevant information")
            print(f"[WEB SEARCH] Preview: {result[:150]}...")
            return result
        else:
            print(f"[WEB SEARCH] ❌ NO DATA: Information not available online")
            return None
        
    except Exception as e:
        print(f"[WEB SEARCH] ❌ ERROR: {e}")
        return None

def llm_reasoning_fallback(query: str, company_name: str, context_preview: str = "") -> Optional[str]:
    """TIER 3: LLM uses reasoning to provide intelligent answer when no direct info available"""
    try:
        print(f"\n[TIER 3: LLM REASONING]")
        print(f"[LLM REASONING] 🧠 Attempting intelligent answer...")
        print(f"[LLM REASONING] Query: {query}")
        
        prompt = f"""You are an intelligent assistant for {company_name}. 

The user asked: "{query}"

Knowledge Base Context (limited): {context_preview[:500] if context_preview else "None"}

Even though you don't have complete information, provide a helpful, intelligent response by:
1. Making reasonable inferences from context
2. Providing general industry knowledge (if applicable)
3. Offering to connect them with someone who has the exact answer
4. Being honest about limitations

Example smart responses:
- "How many attorneys?" + KB has "Michael Carter - Attorney" → "We have at least one attorney, Michael Carter. Let me connect you to get the complete team information."
- "What are your hours?" + No info → "Most legal offices are open 9 AM - 5 PM weekdays. Let me verify our exact hours - what's your phone number?"
- "Do you handle X?" + Similar service in KB → "We handle similar cases in [related area]. Let me check if we can help with your specific situation."

Provide a HELPFUL, SMART answer (2-3 sentences). Don't just say "I don't know."
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an intelligent assistant that provides thoughtful, helpful responses even with limited information."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.6
        )
        
        result = response.choices[0].message.content
        print(f"[LLM REASONING] ✅ SUCCESS: Generated intelligent response")
        print(f"[LLM REASONING] Response: {result[:150]}...")
        return result
        
    except Exception as e:
        print(f"[LLM REASONING] ❌ ERROR: {e}")
        return None

def smart_final_reply(query: str, company_name: str) -> str:
    """TIER 4: Smart final reply when all else fails"""
    print(f"\n[TIER 4: SMART FINAL REPLY]")
    print(f"[FINAL REPLY] 🎯 Generating smart final response...")
    
    # Detect question type and provide contextual response
    query_lower = query.lower()
    
    if any(word in query_lower for word in ['how many', 'how much', 'what is', 'who is', 'who are', 'tell me about']):
        response = f"That's a great question! I want to give you the most accurate information about {company_name}. Let me connect you with someone who can provide those specific details. What's your name and best phone number?"
    elif any(word in query_lower for word in ['can you', 'do you', 'are you able']):
        response = f"I'd love to help you with that! Let me get you connected with our team to discuss your specific needs. What's your name and phone number?"
    elif any(word in query_lower for word in ['price', 'cost', 'fee', 'charge', 'rate']):
        response = f"Pricing depends on your specific situation. Let me have someone reach out to discuss this with you - what's your name and best phone number?"
    elif any(word in query_lower for word in ['location', 'address', 'where are you', 'how do i get']):
        response = f"Let me provide you with our exact location and directions. What's your phone number so we can text you the details?"
    else:
        response = f"I want to make sure you get the right information from {company_name}. Let me connect you with someone who can help. What's your name and phone number?"
    
    print(f"[FINAL REPLY] ✅ Generated contextual response")
    print(f"[FINAL REPLY] Type: {'pricing' if 'cost' in query_lower else 'location' if 'where' in query_lower else 'general'}")
    
    return response

def ask_bot(query: str, session_id: str, api_key: str, user_data: dict = None, **kwargs):
    start_time = time.time()
    
    print(f"\n{'='*80}")
    print(f"[CHATBOT] 🤖 NEW QUERY")
    print(f"[CHATBOT] Session: {session_id}")
    print(f"[CHATBOT] Query: {query}")
    print(f"[CHATBOT] Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # --- 2. Fetch History & Context ---
    chat_history = get_session_history(session_id)
    is_first_message = len(chat_history) == 0
    
    print(f"[HISTORY] Chat history length: {len(chat_history)} messages")
    
    user_context_str = ""
    if user_data:
        name = user_data.get("name", "Friend")
        user_context_str = f"User's Name: {name}"
        print(f"[CONTEXT] User data: {user_context_str}")

    # --- 3. Smart Reformulation (Contextualization) ---
    # This makes the AI understand "How much is it?" based on previous messages.
    reformulated_query = query
    if chat_history:
        rephrase_system = """Given the chat history and the user's latest question, 
        rewrite the question to be standalone and clear. 
        Do not answer it, just clarify what the user is asking."""
        
        rephrase_prompt = ChatPromptTemplate.from_messages([
            ("system", rephrase_system),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])
        
        rephrase_chain = rephrase_prompt | llm | StrOutputParser()
        reformulated_query = rephrase_chain.invoke({
            "chat_history": chat_history,
            "question": query
        })
        print(f"[Smart RAG] Original: '{query}' | Reformulated: '{reformulated_query}'")

    # --- 4. Retrieve Documents with Verification ---
    try:
        query_embedding = embeddings.embed_query(reformulated_query)
        index = pc.Index(index_name)
        
        # Get namespace from kwargs (passed by chatbot service)
        namespace = kwargs.get("vectorStoreId") or kwargs.get("namespace") or "kb_default"
        print(f"[RAG] Namespace: {namespace} | Query: '{reformulated_query[:50]}...'")

        search_results = index.query(
            vector=query_embedding,
            top_k=5,
            namespace=namespace,
            include_metadata=True
        )
        
        # Data verification and quality check
        context_text = ""
        sources = []
        relevant_count = 0
        
        for match in search_results.matches:
            # Verify data quality (score threshold: 0.3+)
            if match.score < 0.3:
                print(f"[RAG] Skipping low-quality match (score: {match.score:.3f})")
                continue
                
            content = match.metadata.get("content", "").strip()
            source = match.metadata.get("title", "Internal Knowledge")
            
            # Verify content is not empty
            if not content or len(content) < 10:
                print(f"[RAG] Skipping empty/invalid content from: {source}")
                continue
            
            relevant_count += 1
            context_text += f"--- Source: {source} ---\n{content}\n\n"
            sources.append(source)
            print(f"[RAG] ✓ Match {relevant_count}: {source} (score: {match.score:.3f})")
            print(f"      Preview: {content[:150]}...")
        
        print(f"[RAG] ✅ Retrieved {relevant_count}/{len(search_results.matches)} relevant documents")
        print(f"[RAG] Context length: {len(context_text)} characters")
        
        # 4-TIER INTELLIGENT ANSWER SYSTEM
        print(f"\n{'='*60}")
        print(f"[4-TIER SYSTEM] Starting intelligent answer search...")
        print(f"{'='*60}")
        
        company_name = kwargs.get("org_name") or kwargs.get("company_name") or "this company"
        web_search_result = None
        llm_reasoning_result = None
        answer_tier = "TIER_1_KB"
        
        # TIER 1: Knowledge Base
        if context_text.strip() and relevant_count > 0:
            print(f"\n[TIER 1: KNOWLEDGE BASE] ✅ SUCCESS")
            print(f"[TIER 1] Found {relevant_count} relevant sources")
            print(f"[TIER 1] Will use KB context for answer")
            answer_tier = "TIER_1_KB"
        else:
            # TIER 2: Web Search
            print(f"\n[TIER 1: KNOWLEDGE BASE] ❌ FAILED - No relevant KB data")
            web_search_result = search_web_for_info(reformulated_query, company_name)
            
            if web_search_result:
                context_text = f"--- Web Search Result ---\n{web_search_result}\n\n"
                print(f"[TIER 2: WEB SEARCH] ✅ SUCCESS - Using web search data")
                answer_tier = "TIER_2_WEB"
            else:
                # TIER 3: LLM Reasoning
                print(f"[TIER 2: WEB SEARCH] ❌ FAILED - No web data found")
                llm_reasoning_result = llm_reasoning_fallback(reformulated_query, company_name, context_text)
                
                if llm_reasoning_result:
                    context_text = f"--- LLM Reasoning ---\n{llm_reasoning_result}\n\n"
                    print(f"[TIER 3: LLM REASONING] ✅ SUCCESS - Using intelligent reasoning")
                    answer_tier = "TIER_3_LLM"
                else:
                    # TIER 4: Smart Final Reply
                    print(f"[TIER 3: LLM REASONING] ❌ FAILED - Cannot reason answer")
                    smart_reply = smart_final_reply(reformulated_query, company_name)
                    context_text = f"--- Smart Final Reply ---\n{smart_reply}\n\n"
                    print(f"[TIER 4: SMART REPLY] ✅ Generated contextual response")
                    answer_tier = "TIER_4_SMART"
        
        print(f"\n{'='*60}")
        print(f"[RESULT] Using {answer_tier} for answer")
        print(f"{'='*60}\n")
        
        # Log for debugging
        if answer_tier in ["TIER_3_LLM", "TIER_4_SMART"]:
            print(f"\n[UNKNOWN QUESTION LOG]")
            print(f"  Session: {session_id}")
            print(f"  Original Query: {query}")
            print(f"  Reformulated: {reformulated_query}")
            print(f"  Namespace: {namespace}")
            print(f"  Answer Tier: {answer_tier}")
            print(f"  KB Results: {relevant_count}")
            print(f"  Web Search: {'SUCCESS' if web_search_result else 'FAILED'}")
            print(f"  LLM Reasoning: {'SUCCESS' if llm_reasoning_result else 'FAILED'}")
            print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"[END LOG]\n")
            
    except Exception as e:
        print(f"[RAG ERROR] ✗ {str(e)}")
        return {"answer": "I'm having trouble accessing information right now. Let me connect you with someone who can help. What's your name and phone number?", "error": str(e)}

    # --- 5. HUMAN-LIKE Adaptive Assistant (Professional, Natural, Proactive) ---
    
    system_template = """You are a professional customer support specialist for {company_name}. You communicate like a knowledgeable, friendly human - NOT a robot or AI assistant.

    🎯 YOUR MISSION: Help visitors naturally while gathering their contact information (Name, Phone, Specific Need).

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    📝 RESPONSE STRUCTURE (Use ALWAYS for every answer):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    1️⃣ **DIRECT ANSWER FIRST** (1 sentence)
       - Answer their exact question immediately
       - Be specific and clear
       - Example: "Yes, we have 3 experienced attorneys on our team."
       - Example: "We're open Monday-Friday, 9 AM to 6 PM."
    
    2️⃣ **HELPFUL CONTEXT** (1-2 sentences)
       - Add relevant details that enhance the answer
       - Mention related services/products/benefits
       - Show expertise and build trust
       - Example: "Our founder, Michael Carter, has been practicing personal injury law for over 15 years, specializing in car accidents and workplace injuries."
       - Example: "We also offer evening consultations by appointment for clients who can't make it during regular hours."
    
    3️⃣ **SMART ENGAGEMENT** (1 question)
       - Predict what they'll ask next or need
       - Move conversation forward naturally
       - Guide toward booking/purchase/contact
       - Example: "What type of case brings you here today?"
       - Example: "Would you like to schedule a consultation this week?"
       - Example: "Are you looking for delivery or pickup?"

    🚨 CRITICAL: Your responses must flow like a REAL CONVERSATION, not robotic AI dumps.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🧠 INTELLIGENT CONTEXT SYNTHESIS:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    ✅ **MERGE MULTIPLE SOURCES** - Don't just copy-paste context:
       - Read ALL context sources provided
       - Combine related information from different sources
       - Synthesize into ONE coherent, natural answer
       - Remove redundancy and contradictions
    
    ✅ **INTELLIGENT ANALYSIS**:
       - COUNT: "How many?" → Count all relevant items in context
       - LIST: "Who are?" → Extract and list all names/items
       - COMPARE: "Best option?" → Analyze and recommend
       - SUMMARIZE: "Tell me about" → Synthesize key points
       - EXPLAIN: "How does it work?" → Break down process
    
    ✅ **EXTRACT & COMBINE**:
       - Names, roles, credentials, experience
       - Services, products, features, benefits
       - Prices, hours, locations, contact info
       - Policies, processes, timelines
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎭 FIRST MESSAGE GREETING (if this is user's first interaction):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    Structure: **Greeting + What We Do + Engaging Question**
    
    Examples by business type (ADAPT based on context):
    
    🏛️ **Law Firm**: "Hi! I'm here to help with {company_name}. We specialize in personal injury cases including car accidents, workplace injuries, and medical malpractice. Were you or someone you know recently injured in an accident?"
    
    🍽️ **Restaurant**: "Welcome to {company_name}! We serve authentic Italian cuisine with fresh, locally-sourced ingredients. Are you looking to make a reservation or place a takeout order?"
    
    🏥 **Medical/Dental**: "Hello! Thanks for visiting {company_name}. We provide comprehensive family healthcare with same-day appointments available. What brings you in today - scheduling an appointment or general questions?"
    
    🛍️ **Retail/E-commerce**: "Hi there! Welcome to {company_name}. We offer premium [products] with free shipping on orders over $50. What are you shopping for today?"
    
    🏠 **Real Estate**: "Hello! I'm with {company_name}. We help clients buy, sell, and rent properties throughout [area]. Are you looking to buy, sell, or rent?"
    
    💻 **Software/SaaS**: "Hi! Welcome to {company_name}. We help businesses [solve problem] with our [solution]. What challenge are you trying to solve?"
    
    📋 **Consulting/Services**: "Hello! I'm with {company_name}. We specialize in [services] for [target clients]. What kind of help are you looking for?"
    
    🎯 **General**: "Hi! Thanks for visiting {company_name}. How can I help you today?"

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎯 PROACTIVE CONVERSATION FLOW (Predict Next Steps):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    Track conversation progress and guide naturally:
    
    📍 **Stage 1 - Discovery** (Initial questions):
       - Answer their question
       - Add helpful context
       - Ask about their specific need/interest
    
    📍 **Stage 2 - Qualification** (2nd-3rd exchange):
       - Answer with more detail
       - Mention relevant options/solutions
       - Ask qualifying questions (timing, budget, specifics)
    
    📍 **Stage 3 - Action** (3rd-4th exchange):
       - Provide solution/recommendation
       - Create urgency or value
       - Request contact info: "Let me connect you with [person/team]. What's your name and best phone number?"
    
    📍 **Smart Next Questions** (Predict based on their question):
       - They ask about services → Ask: "Which service interests you most?"
       - They ask about pricing → Ask: "When are you looking to get started?"
       - They ask about location → Ask: "Would you like to schedule a visit?"
       - They ask about team → Ask: "Would you like to speak with one of them?"
       - They ask about hours → Ask: "What day works best for you?"
       - They ask about process → Ask: "Ready to take the first step?"

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    💬 CONVERSATIONAL INTELLIGENCE:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    ✅ **SOUND HUMAN** (Never robotic):
       - Use contractions: "We're", "I'll", "You'll", "That's"
       - Vary sentence structure: Don't start every sentence the same way
       - Show personality: Friendly, helpful, professional
       - Use transitions: "Also", "Plus", "By the way", "Speaking of"
    
    ✅ **BE CONCISE** (2-4 sentences total):
       - Direct answer (1 sentence)
       - Context/explanation (1-2 sentences)
       - Engaging question (1 sentence)
       - NO long paragraphs or bullet lists
    
    ✅ **ADAPT TONE** (Match the visitor):
       - Urgent/Stressed → Empathetic and fast
       - Casual/Friendly → Warm and conversational
       - Professional/Formal → Polished and respectful
       - Confused → Patient and clear
    
    ✅ **BUILD TRUST**:
       - Show expertise without bragging
       - Be honest about limitations
       - Offer alternatives when needed
       - Never make up information
    
    ❌ **AVOID ROBOTIC PATTERNS**:
       - Don't start with "Sure!" or "Absolutely!" every time
       - Don't repeat the user's question back
       - Don't use "I'd be happy to" repeatedly
       - Don't list sources or say "According to our data"
       - Don't sound like you're reading a script

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎯 HANDLING MISSING INFORMATION:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    ❌ ONLY say "I don't have that information" IF:
       - Context is completely empty
       - Context explicitly says "[NO INFORMATION AVAILABLE]"
       - Question is completely unrelated to available context
    
    ✅ THEN provide smart response:
       "I don't have that specific detail on hand, but I can connect you with someone who does. What's your name and best phone number?"

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    📊 CONTEXT DATA (Synthesize & Use Intelligently):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    {user_context}

    === AVAILABLE INFORMATION ===
    {context}
    ============================
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ✅ FINAL REMINDER:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. Answer → Context → Question (3-part structure)
    2. Synthesize multiple sources (don't just copy-paste)
    3. Sound like a HUMAN, not an AI (use contractions, vary style)
    4. Predict next question (be proactive)
    5. Keep responses SHORT (2-4 sentences)
    6. Guide toward contact collection (Name, Phone)
    7. Adapt to ANY business type (law, medical, retail, restaurant, etc.)
    
    You are NOT an AI assistant. You are a knowledgeable team member having a natural conversation.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    chain = prompt | llm | StrOutputParser()
    
    # Get company name from kwargs
    company_name = kwargs.get("org_name") or kwargs.get("company_name") or "our office"

    print(f"[GENERATION] Generating response...")
    print(f"[GENERATION] Company: {company_name}")
    print(f"[GENERATION] Context length: {len(context_text)} chars")
    print(f"[GENERATION] First message: {is_first_message}")
    
    answer = chain.invoke({
        "company_name": company_name,
        "context": context_text,
        "chat_history": chat_history,
        "question": query, 
        "user_context": user_context_str
    })

    print(f"[GENERATION] ✓ Response generated: {answer[:100]}...")

    # --- 6. Save Memory ---
    save_to_history(session_id, query, answer)
    
    elapsed = time.time() - start_time
    print(f"[COMPLETE] ✓ Total time: {elapsed:.2f}s")
    print(f"{'='*80}\n")

    # Determine response type for logging
    print(f"\n[FINAL RESPONSE DETAILS]")
    print(f"[RESPONSE] Answer Tier: {answer_tier}")
    print(f"[RESPONSE] Sources: {len(sources)} sources")
    print(f"[RESPONSE] First Message: {is_first_message}")
    print(f"[RESPONSE] Web Search Used: {web_search_result is not None}")
    print(f"[RESPONSE] LLM Reasoning Used: {llm_reasoning_result is not None}")
    print(f"[RESPONSE] Total Time: {elapsed:.2f}s")

    return {
        "answer": answer,
        "sources": list(set(sources)) if sources else ["AI Assistant"],
        "session_id": session_id,
        "response_type": answer_tier,
        "answer_tier": answer_tier,
        "is_first_message": is_first_message,
        "used_web_search": web_search_result is not None,
        "used_llm_reasoning": llm_reasoning_result is not None,
        "kb_match_count": relevant_count if 'relevant_count' in locals() else 0
    }
