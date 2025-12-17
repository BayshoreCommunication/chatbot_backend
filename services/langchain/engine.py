import os
import time
from typing import List, Dict
from dotenv import load_dotenv

# LangChain & Pinecone Imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pinecone import Pinecone

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

def ask_bot(query: str, session_id: str, api_key: str, user_data: dict = None, **kwargs):
    start_time = time.time()
    
    # --- 2. Fetch History & Context ---
    chat_history = get_session_history(session_id)
    
    user_context_str = ""
    if user_data:
        name = user_data.get("name", "Friend")
        user_context_str = f"User's Name: {name}"

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
        
        print(f"[RAG] Retrieved {relevant_count} relevant documents (from {len(search_results.matches)} total)")
        
        # If no relevant context found, make it explicit
        if not context_text.strip():
            context_text = "[NO RELEVANT CONTEXT FOUND - Inform user and offer to connect with attorney]"
            print(f"[RAG] ⚠️ No relevant context found for query")
            
    except Exception as e:
        print(f"[RAG ERROR] {str(e)}")
        return {"answer": "I'm having trouble accessing information right now. Let me connect you with someone who can help. What's your name and phone number?", "error": str(e)}

    # --- 5. Lead-Generation System Prompt ---
    
    system_template = """You are a lead-generation specialist for {company_name}. Your job is to qualify potential clients naturally while being helpful.

    🚨 CRITICAL - CONTEXT ONLY RULE:
    - Answer ONLY using facts from the Context Data below
    - If the answer is NOT in Context Data, say: "I don't have that specific detail, but let me connect you with someone who can help"
    - NEVER make up information, guess, or use general knowledge
    - If Context Data is empty or irrelevant, acknowledge you need to get help from the team
    
    💬 CONVERSATION STYLE:
    1. **Keep it SHORT** - 2-3 sentences MAX. No essays.
    2. **Natural Tone** - Talk like a helpful human, not a robot. Vary your language.
    3. **Lead Qualification Focus** - Your goal is to collect: Name, Phone, Accident Type, Date, Injuries
    4. **Smooth Transitions** - Guide conversation naturally toward getting their contact info
    
    🎯 SMART NEXT STEPS (Predict what to ask based on their answer):
    - First message / General inquiry → "Were you or someone you know injured in an accident? Car / Fall / Work / Medical / Other"
    - Mentions accident/injury → Ask accident TYPE
    - Shares accident type → Ask WHEN it happened
    - Shares timing → Ask if INJURED / needed medical attention (Yes/No)
    - Confirms injury → Ask about POLICE REPORT (Yes/No)
    - After 2-3 exchanges → Ask for NAME and PHONE to connect with attorney
    - Cost/consultation questions → "Free consultation, no fee unless we win. Want to speak with an attorney now?"
    - Info not available → "Let me connect you with an attorney who has that answer. What's your name and best number?"
    
    🎭 TONE DETECTION & RESPONSE:
    - Urgent/Distressed → Be empathetic: "I'm so sorry to hear that. Let's get you help right away."
    - Casual/Browsing → Be friendly: "Happy to help! Let me know what you need."
    - Frustrated → Be reassuring: "I understand. Let me make this easy for you."
    - Professional → Match their tone: "Absolutely. Here's what you need to know."
    
    {user_context}

    === Context Data (USE ONLY THIS) ===
    {context}
    ========================================
    
    Remember: CONTEXT ONLY. NATURAL FLOW. COLLECT LEAD INFO. Match their energy.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    chain = prompt | llm | StrOutputParser()
    
    # Get company name from kwargs
    company_name = kwargs.get("org_name") or kwargs.get("company_name") or "our office"

    answer = chain.invoke({
        "company_name": company_name,
        "context": context_text,
        "chat_history": chat_history,
        "question": query, 
        "user_context": user_context_str
    })

    # --- 6. Save Memory ---
    save_to_history(session_id, query, answer)
    
    elapsed = time.time() - start_time
    print(f"[Smart RAG] Answer generated in {elapsed:.2f}s")

    return {
        "answer": answer,
        "sources": list(set(sources)),
        "session_id": session_id
    }
