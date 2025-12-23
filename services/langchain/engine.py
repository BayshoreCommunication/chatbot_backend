import os
import time
import json
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from openai import OpenAI

# LangChain Core Imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnablePassthrough
from pinecone import Pinecone

# Import all prompts from centralized location
from .prompts import (
    REPHRASE_SYSTEM_PROMPT,
    get_web_search_prompt,
    WEB_SEARCH_SYSTEM_PROMPT,
    get_llm_reasoning_prompt,
    LLM_REASONING_SYSTEM_PROMPT,
    SMART_REPLY_PATTERNS,
    MAIN_SYSTEM_PROMPT,
    RAG_AGENT_PROMPT,
    RAG_ERROR_MESSAGE
)

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

# =============================================================================
# LANGCHAIN TOOLS FOR RAG AGENT
# =============================================================================

# Global variables for tools
_current_namespace = "kb_default"
_current_company_name = "this company"
_current_chat_history = []

def set_tool_context(namespace: str, company_name: str, chat_history: List = None):
    """Set context for tools including full conversation history"""
    global _current_namespace, _current_company_name, _current_chat_history
    _current_namespace = namespace
    _current_company_name = company_name
    _current_chat_history = chat_history if chat_history else []
    
    print(f"[TOOL CONTEXT] Updated context:")
    print(f"[TOOL CONTEXT]   Namespace: {namespace}")
    print(f"[TOOL CONTEXT]   Company: {company_name}")
    print(f"[TOOL CONTEXT]   Conversation history: {len(_current_chat_history)} messages")

@tool
def search_knowledge_base_primary(query: str) -> str:
    """
    STEP 1: Primary search in the knowledge base with standard parameters.
    Use this tool FIRST to find information about services, products, team, hours, location, etc.
    This tool searches both the knowledge base AND the full conversation history.
    
    Args:
        query: The search query to find relevant information
        
    Returns:
        Relevant information from knowledge base and conversation history, or empty string if not found
    """
    try:
        print(f"\n[TOOL: PRIMARY KB SEARCH]")
        print(f"[PRIMARY KB] Query: {query}")
        
        # Search conversation history first
        conversation_context = []
        if _current_chat_history:
            print(f"[PRIMARY KB] Searching conversation history ({len(_current_chat_history)} messages)...")
            for msg in _current_chat_history:
                if isinstance(msg, HumanMessage):
                    # Check if query relates to previous user questions
                    if any(word.lower() in msg.content.lower() for word in query.lower().split()):
                        conversation_context.append(f"Previous User Query: {msg.content}")
                elif isinstance(msg, AIMessage):
                    # Check if previous AI responses are relevant
                    if any(word.lower() in msg.content.lower() for word in query.lower().split()):
                        conversation_context.append(f"Previous AI Response: {msg.content}")
        
        if conversation_context:
            print(f"[PRIMARY KB] ✓ Found {len(conversation_context)} relevant messages in conversation history")
        
        # Search knowledge base
        query_embedding = embeddings.embed_query(query)
        index = pc.Index(index_name)
        
        search_results = index.query(
            vector=query_embedding,
            top_k=5,
            namespace=_current_namespace,
            include_metadata=True
        )
        
        # DEBUG: Log all results before filtering
        print(f"[PRIMARY KB] Raw search results: {len(search_results.matches)} total matches")
        for idx, match in enumerate(search_results.matches):
            print(f"[PRIMARY KB]   Match {idx+1}: score={match.score:.4f}, title={match.metadata.get('title', 'N/A')[:50]}")
        
        context_parts = []
        relevant_count = 0
        
        for match in search_results.matches:
            if match.score < 0.25:  # Lowered threshold from 0.3 to 0.25 for better recall
                print(f"[PRIMARY KB] ⏭️ Skipping match with score {match.score:.4f} (below threshold 0.25)")
                continue
                
            content = match.metadata.get("content", "").strip()
            source = match.metadata.get("title", "Internal Knowledge")
            
            if content and len(content) > 10:
                relevant_count += 1
                context_parts.append(f"Source: {source}\n{content}")
                print(f"[PRIMARY KB] ✓ Match {relevant_count}: {source} (score: {match.score:.3f})")
        
        # Combine conversation history and knowledge base results
        all_context = []
        
        if conversation_context:
            all_context.append("=== CONVERSATION HISTORY ===")
            all_context.extend(conversation_context[:3])  # Top 3 relevant from history
        
        if context_parts:
            all_context.append("\n=== KNOWLEDGE BASE ===")
            all_context.extend(context_parts)
        
        if all_context:
            result = "\n\n".join(all_context)
            print(f"[PRIMARY KB] ✅ Found {relevant_count} KB docs + {len(conversation_context)} history items")
            return result
        else:
            print(f"[PRIMARY KB] ❌ No relevant information found")
            return ""
            
    except Exception as e:
        print(f"[PRIMARY KB] ❌ ERROR: {e}")
        return ""

@tool
def search_knowledge_base_detailed(query: str) -> str:
    """
    STEP 2: Detailed search in knowledge base with lower threshold and more results.
    Use this tool if primary search didn't find enough information.
    This searches more broadly in both knowledge base AND full conversation history.
    
    Args:
        query: The search query, can be reformulated or expanded
        
    Returns:
        Additional relevant information or empty string if not found
    """
    try:
        print(f"\n[TOOL: DETAILED KB SEARCH]")
        print(f"[DETAILED KB] Query: {query}")
        
        # Deep search in conversation history
        conversation_context = []
        if _current_chat_history:
            print(f"[DETAILED KB] Deep search in conversation history ({len(_current_chat_history)} messages)...")
            # More lenient matching for detailed search
            for msg in _current_chat_history:
                content_lower = msg.content.lower()
                # Include more messages with partial matches
                if any(word.lower() in content_lower for word in query.lower().split() if len(word) > 3):
                    if isinstance(msg, HumanMessage):
                        conversation_context.append(f"User said: {msg.content}")
                    elif isinstance(msg, AIMessage):
                        conversation_context.append(f"AI replied: {msg.content}")
        
        if conversation_context:
            print(f"[DETAILED KB] ✓ Found {len(conversation_context)} related messages in history")
        
        # Detailed knowledge base search
        query_embedding = embeddings.embed_query(query)
        index = pc.Index(index_name)
        
        # More aggressive search with lower threshold and more results
        search_results = index.query(
            vector=query_embedding,
            top_k=10,
            namespace=_current_namespace,
            include_metadata=True
        )
        
        context_parts = []
        relevant_count = 0
        
        for match in search_results.matches:
            # Lower threshold for detailed search
            if match.score < 0.2:
                continue
                
            content = match.metadata.get("content", "").strip()
            source = match.metadata.get("title", "Internal Knowledge")
            
            if content and len(content) > 10:
                relevant_count += 1
                context_parts.append(f"Source: {source}\n{content}")
                print(f"[DETAILED KB] ✓ Match {relevant_count}: {source} (score: {match.score:.3f})")
        
        # Combine all findings
        all_context = []
        
        if conversation_context:
            all_context.append("=== FULL CONVERSATION HISTORY ===")
            all_context.extend(conversation_context[:5])  # Top 5 from history
        
        if context_parts:
            all_context.append("\n=== ADDITIONAL KNOWLEDGE BASE RESULTS ===")
            all_context.extend(context_parts)
        
        if all_context:
            result = "\n\n".join(all_context)
            print(f"[DETAILED KB] ✅ Found {relevant_count} KB docs + {len(conversation_context)} history items")
            return result
        else:
            print(f"[DETAILED KB] ❌ No additional information found")
            return ""
            
    except Exception as e:
        print(f"[DETAILED KB] ❌ ERROR: {e}")
        return ""

@tool
def merge_and_synthesize_information(primary_info: str, detailed_info: str, user_question: str) -> str:
    """
    STEP 3: Merge and synthesize information from multiple sources.
    Use this tool to combine information from primary and detailed searches.
    This will create a coherent, comprehensive answer from multiple sources.
    
    Args:
        primary_info: Information from primary search
        detailed_info: Information from detailed search
        user_question: The original user question
        
    Returns:
        Synthesized and merged information
    """
    try:
        print(f"\n[TOOL: MERGE & SYNTHESIZE]")
        print(f"[MERGE] Combining information from multiple sources")
        
        if not primary_info and not detailed_info:
            print(f"[MERGE] ⚠️ No information to merge")
            return ""
        
        # Combine all available information
        all_info = []
        if primary_info:
            all_info.append(primary_info)
        if detailed_info:
            all_info.append(detailed_info)
        
        combined = "\n\n---\n\n".join(all_info)
        
        # Use LLM to synthesize
        synthesis_prompt = f"""Analyze and synthesize the following information to answer the user's question.

User Question: {user_question}

Available Information:
{combined}

Instructions:
1. Extract the most relevant facts
2. Remove redundant information
3. Organize information logically
4. Present in a clear, natural way
5. Only include verified facts from the sources

Synthesized Answer:"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at synthesizing information from multiple sources."},
                {"role": "user", "content": synthesis_prompt}
            ],
            max_tokens=400,
            temperature=0.3
        )
        
        result = response.choices[0].message.content
        print(f"[MERGE] ✅ Successfully synthesized information")
        return result
        
    except Exception as e:
        print(f"[MERGE] ❌ ERROR: {e}")
        return primary_info or detailed_info or ""

@tool
def search_web_for_company_info(query: str) -> str:
    """
    STEP 2B: Search the web for public information about the company.
    Use this tool if knowledge base search didn't find information.
    This searches for publicly available information online.
    
    Args:
        query: The search query about the company
        
    Returns:
        Public information found online or empty string if not found
    """
    try:
        print(f"\n[TOOL: WEB SEARCH]")
        print(f"[WEB SEARCH] Query: {query}")
        print(f"[WEB SEARCH] Company: {_current_company_name}")
        
        prompt = get_web_search_prompt(query, _current_company_name)

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": WEB_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        
        result = response.choices[0].message.content
        
        # Check if it's a "not found" response
        if "not publicly available" in result.lower() or "not found" in result.lower():
            print(f"[WEB SEARCH] ❌ No public information found")
            return ""
        
        print(f"[WEB SEARCH] ✅ Found public information")
        return f"=== PUBLIC INFORMATION (Web Search) ===\n{result}"
        
    except Exception as e:
        print(f"[WEB SEARCH] ❌ ERROR: {e}")
        return ""

@tool
def generate_helpful_fallback_response(user_question: str) -> str:
    """
    FINAL STEP: Generate a helpful response when no information is available.
    Use this tool as a last resort when knowledge base has no relevant information.
    This provides a professional, helpful response without making up facts.
    
    Args:
        user_question: The user's original question
        
    Returns:
        A helpful, honest response acknowledging the limitation
    """
    try:
        print(f"\n[TOOL: FALLBACK RESPONSE]")
        print(f"[FALLBACK] Generating helpful response for: {user_question}")
        
        fallback_prompt = f"""The user asked: "{user_question}"

We don't have specific information about this in our knowledge base.

Generate a helpful, professional response that:
1. Acknowledges we don't have that specific information
2. Offers to connect them with someone who can help
3. Sounds natural and human
4. Doesn't apologize excessively
5. Keeps it brief (2-3 sentences)

Response:"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional customer service representative."},
                {"role": "user", "content": fallback_prompt}
            ],
            max_tokens=150,
            temperature=0.6
        )
        
        result = response.choices[0].message.content
        print(f"[FALLBACK] ✅ Generated fallback response")
        return result
        
    except Exception as e:
        print(f"[FALLBACK] ❌ ERROR: {e}")
        return "I don't have that specific information available right now. Let me connect you with someone from our team who can help. What's your name and phone number?"

# Create tools list - ORDER MATTERS (primary → detailed → web → merge → fallback)
rag_tools = [
    search_knowledge_base_primary,
    search_knowledge_base_detailed,
    search_web_for_company_info,
    merge_and_synthesize_information,
    generate_helpful_fallback_response
]

# =============================================================================
# RAG AGENT CREATION
# =============================================================================

def create_rag_agent():
    """
    Create a tool-calling chain for RAG using LangChain 1.2+ pattern.
    This uses the bind_tools() method instead of deprecated AgentExecutor.
    """
    try:
        # Bind tools to the LLM
        llm_with_tools = llm.bind_tools(rag_tools)
        
        # Create the agent prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_AGENT_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{question}")
        ])
        
        # Create the chain: prompt -> llm_with_tools -> output
        agent_chain = prompt | llm_with_tools
        
        print("[RAG AGENT] ✅ Agent created successfully using LangChain 1.2+ pattern")
        return agent_chain
        
    except Exception as e:
        print(f"[RAG AGENT] ⚠️ Failed to create agent: {e}")
        return None

# =============================================================================
# ORIGINAL HELPER FUNCTIONS (kept for backward compatibility)
# =============================================================================

def search_web_for_info(query: str, company_name: str) -> Optional[str]:
    """TIER 2: Search web for information not in knowledge base"""
    try:
        print(f"\n[TIER 2: WEB SEARCH]")
        print(f"[WEB SEARCH] 🔍 Query: {query}")
        print(f"[WEB SEARCH] 🏢 Company: {company_name}")
        
        prompt = get_web_search_prompt(query, company_name)

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": WEB_SEARCH_SYSTEM_PROMPT},
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
        
        prompt = get_llm_reasoning_prompt(query, company_name, context_preview)

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": LLM_REASONING_SYSTEM_PROMPT},
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
    
    # Check patterns and return appropriate response
    for pattern_name, pattern_data in SMART_REPLY_PATTERNS.items():
        if pattern_name == "default":
            continue
        if any(word in query_lower for word in pattern_data["keywords"]):
            response = pattern_data["template"].format(company_name=company_name)
            print(f"[FINAL REPLY] ✅ Generated contextual response")
            print(f"[FINAL REPLY] Type: {pattern_name}")
            return response
    
    # Default fallback
    response = SMART_REPLY_PATTERNS["default"]["template"].format(company_name=company_name)
    print(f"[FINAL REPLY] ✅ Generated contextual response")
    print(f"[FINAL REPLY] Type: default")
    
    return response

def ask_bot(query: str, session_id: str, api_key: str, user_data: dict = None, **kwargs):
    start_time = time.time()
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    
    print(f"\n{'='*80}")
    print(f"[CHATBOT] 🤖 NEW QUERY")
    print(f"[CHATBOT] Session: {session_id}")
    print(f"[CHATBOT] Query: {query}")
    print(f"[CHATBOT] Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # --- 1. Fetch History & Context ---
    chat_history = get_session_history(session_id)
    is_first_message = len(chat_history) == 0
    
    print(f"[HISTORY] Chat history length: {len(chat_history)} messages")
    print(f"[HISTORY] Chat history summary: {len(chat_history)} turns")
    
    # Log conversation history for debugging
    if chat_history:
        print(f"[HISTORY] Conversation context:")
        for i, msg in enumerate(chat_history[-4:], 1):  # Show last 4 messages
            role = "User" if isinstance(msg, HumanMessage) else "AI"
            preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
            print(f"[HISTORY]   {role}: {preview}")
    
    user_context_str = ""
    if user_data:
        name = user_data.get("name", "Friend")
        phone = user_data.get("phone", "")
        user_context_str = f"User's Name: {name}"
        if phone:
            user_context_str += f", Phone: {phone}"
        print(f"[CONTEXT] User data: {user_context_str}")

    # --- 2. Smart Reformulation (Contextualization) ---
    reformulated_query = query
    if chat_history:
        rephrase_prompt = ChatPromptTemplate.from_messages([
            ("system", REPHRASE_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])
        
        rephrase_chain = rephrase_prompt | llm | StrOutputParser()
        
        # Track tokens for rephrase
        print(f"[REPHRASE] Reformulating query with conversation context...")
        rephrase_response = rephrase_chain.invoke({
            "chat_history": chat_history,
            "question": query
        })
        
        reformulated_query = rephrase_response
        
        # Estimate tokens (rough estimate: 1 token ≈ 4 characters)
        rephrase_tokens = len(str(chat_history) + query + reformulated_query) // 4
        total_tokens += rephrase_tokens
        print(f"[REPHRASE] Tokens used (estimated): {rephrase_tokens}")
        print(f"[REPHRASE] Original: '{query}'")
        print(f"[REPHRASE] Reformulated: '{reformulated_query}'")

    # --- 3. Set Context for Tools ---
    namespace = kwargs.get("vectorStoreId") or kwargs.get("namespace") or "kb_default"
    company_name = kwargs.get("org_name") or kwargs.get("company_name") or "this company"
    set_tool_context(namespace, company_name, chat_history)  # Pass full conversation history to tools
    
    print(f"[CONTEXT] Namespace: {namespace}")
    print(f"[CONTEXT] Company: {company_name}")
    print(f"[CONTEXT] Full conversation history available to agent: {len(chat_history)} messages")
    print(f"[CONTEXT] Tools can now search conversation history as knowledge base")

    # --- 4. MANDATORY CASCADING SEARCH (KB → Web → Fallback) ---
    agent_answer = ""
    used_agent = True
    agent_tokens = 0
    search_tier = "NONE"
    all_search_results = []
    
    try:
        print(f"\n[CASCADING SEARCH] Starting mandatory multi-tier search...")
        print(f"[CASCADING SEARCH] Will try: KB Primary → KB Detailed → Web Search → Merge/Fallback")
        
        # TIER 1: PRIMARY KB SEARCH
        print(f"\n[TIER 1] PRIMARY KB SEARCH")
        primary_result = search_knowledge_base_primary.func(query=reformulated_query)
        
        if primary_result and len(primary_result.strip()) > 50:
            all_search_results.append(("PRIMARY_KB", primary_result))
            print(f"[TIER 1] ✅ Found data in primary search ({len(primary_result)} chars)")
        else:
            print(f"[TIER 1] ⚠️ INSUFFICIENT - Primary search returned little/no data")
        
        # TIER 2: DETAILED KB SEARCH (always try for better coverage)
        print(f"\n[TIER 2] DETAILED KB SEARCH")
        detailed_result = search_knowledge_base_detailed.func(query=reformulated_query)
        
        if detailed_result and len(detailed_result.strip()) > 50:
            all_search_results.append(("DETAILED_KB", detailed_result))
            print(f"[TIER 2] ✅ Found data in detailed search ({len(detailed_result)} chars)")
        else:
            print(f"[TIER 2] ⚠️ INSUFFICIENT - Detailed search returned little/no data")
        
        # TIER 3: WEB SEARCH (try if KB results are weak)
        if len(all_search_results) < 2:
            print(f"\n[TIER 3] WEB SEARCH (KB results insufficient)")
            web_result = search_web_for_company_info.func(query=reformulated_query)
            
            if web_result and len(web_result.strip()) > 50:
                all_search_results.append(("WEB_SEARCH", web_result))
                print(f"[TIER 3] ✅ Found data via web search ({len(web_result)} chars)")
            else:
                print(f"[TIER 3] ⚠️ INSUFFICIENT - Web search returned little/no data")
        else:
            print(f"\n[TIER 3] SKIPPING WEB SEARCH - KB results sufficient")
        
        # DECISION: Merge or Fallback
        if all_search_results:
            if len(all_search_results) > 1:
                # TIER 4A: MERGE MULTIPLE SOURCES
                print(f"\n[TIER 4A] MERGING {len(all_search_results)} SOURCES")
                
                # Organize results by type
                primary_info = ""
                detailed_info = ""
                for src, content in all_search_results:
                    if "PRIMARY" in src:
                        primary_info = content
                    else:
                        detailed_info += f"\n\n[{src}]\n{content}"
                
                merge_result = merge_and_synthesize_information.func(
                    primary_info=primary_info or "No primary KB data",
                    detailed_info=detailed_info or "No additional data",
                    user_question=query
                )
                agent_answer = merge_result
                search_tier = "MERGED_" + "+".join([src for src, _ in all_search_results])
                print(f"[TIER 4A] ✅ Merged {len(all_search_results)} sources into cohesive answer")
            else:
                # Single source - use directly
                search_tier, agent_answer = all_search_results[0]
                print(f"[TIER 4A] ✅ Using single source: {search_tier}")
        else:
            # TIER 4B: FALLBACK RESPONSE
            print(f"\n[TIER 4B] GENERATING FALLBACK (no data found)")
            fallback_result = generate_helpful_fallback_response.func(user_question=query)
            agent_answer = fallback_result
            search_tier = "FALLBACK"
            print(f"[TIER 4B] ✅ Generated helpful fallback response")
        
        # Track estimated tokens
        agent_tokens = len(reformulated_query + str(agent_answer)) // 4
        total_tokens += agent_tokens
        
        print(f"\n[CASCADING SEARCH] ✅ COMPLETE")
        print(f"[CASCADING SEARCH] Final tier: {search_tier}")
        print(f"[CASCADING SEARCH] Sources used: {len(all_search_results)}")
        print(f"[CASCADING SEARCH] Result length: {len(agent_answer)} chars")
        
    except Exception as e:
        print(f"[CASCADING SEARCH] ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        agent_answer = ""
        search_tier = "ERROR"

    # --- 5. Format Response with Main System Prompt ---
    if agent_answer and agent_answer.strip():
        # Use the agent's findings as context for the main response
        context_text = f"=== RESEARCH FINDINGS ===\n{agent_answer}\n"
        print(f"[CONTEXT] ✅ Using research findings: {len(agent_answer)} chars")
    else:
        context_text = "=== NO INFORMATION AVAILABLE ===\nNo relevant information found in knowledge base.\n"
        print(f"[CONTEXT] ⚠️ NO INFORMATION FOUND")
        print(f"[CONTEXT] This usually means:")
        print(f"[CONTEXT]   1. Knowledge base namespace '{namespace}' has no data")
        print(f"[CONTEXT]   2. Or search query didn't match any content")
        print(f"[CONTEXT]   3. Check if correct namespace/org ID was provided")
    
    print(f"\n[GENERATION] Generating final response with main prompt...")
    print(f"[GENERATION] Context length: {len(context_text)} chars")
    print(f"[GENERATION] First message: {is_first_message}")
    print(f"[GENERATION] Full conversation history in context: {len(chat_history)} messages")
    
    # Create final response using main system prompt WITH FULL CONVERSATION HISTORY
    prompt = ChatPromptTemplate.from_messages([
        ("system", MAIN_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{question}")
    ])

    chain = prompt | llm | StrOutputParser()
    
    final_answer = chain.invoke({
        "company_name": company_name,
        "context": context_text,
        "chat_history": chat_history,  # Full conversation history passed to final generation
        "question": query,
        "user_context": user_context_str
    })

    # Track tokens for final generation
    final_gen_tokens = len(context_text + str(chat_history) + query + final_answer) // 4
    total_tokens += final_gen_tokens
    print(f"[GENERATION] Tokens used (estimated): {final_gen_tokens}")
    print(f"[GENERATION] ✓ Final response generated: {final_answer[:100]}...")

    # --- 6. Save Memory ---
    save_to_history(session_id, query, final_answer)
    
    elapsed = time.time() - start_time
    print(f"[COMPLETE] ✓ Total time: {elapsed:.2f}s")
    print(f"{'='*80}\n")

    # Response metadata with token tracking
    print(f"\n[FINAL RESPONSE DETAILS]")
    print(f"[RESPONSE] Mode: {'RAG Agent with Tools' if used_agent else 'Legacy Direct Search'}")
    print(f"[RESPONSE] First Message: {is_first_message}")
    print(f"[RESPONSE] Total Time: {elapsed:.2f}s")
    print(f"\n[TOKEN USAGE BREAKDOWN]")
    print(f"[TOKENS] Rephrase: {total_tokens - agent_tokens - final_gen_tokens if chat_history else 0} tokens")
    print(f"[TOKENS] Agent/Tools: {agent_tokens} tokens")
    print(f"[TOKENS] Final Generation: {final_gen_tokens} tokens")
    print(f"[TOKENS] TOTAL ESTIMATED: {total_tokens} tokens")
    print(f"[TOKENS] Cost (GPT-4o-mini): ~${(total_tokens / 1000000) * 0.15:.6f} USD")

    return {
        "answer": final_answer,
        "sources": [f"Cascading Search - {search_tier}"],
        "session_id": session_id,
        "response_type": "CASCADING_SEARCH",
        "answer_tier": search_tier,
        "is_first_message": is_first_message,
        "used_agent": used_agent,
        "total_time": elapsed,
        "token_usage": {
            "total_tokens": total_tokens,
            "rephrase_tokens": total_tokens - agent_tokens - final_gen_tokens if chat_history else 0,
            "agent_tokens": agent_tokens,
            "generation_tokens": final_gen_tokens,
            "estimated_cost_usd": round((total_tokens / 1000000) * 0.15, 6)
        },
        "conversation_context": {
            "history_length": len(chat_history),
            "is_first_message": is_first_message,
            "user_data": user_data if user_data else None
        },
        "search_details": {
            "tier_used": search_tier,
            "namespace": namespace,
            "company": company_name
        }
    }
