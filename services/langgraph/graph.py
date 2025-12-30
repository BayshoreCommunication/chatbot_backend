"""
Enhanced LangGraph Workflow (V3)
Improvements over V2:
1. Query rewriting for context-dependent questions
2. Conversation summarization for long conversations
3. Better conversation context management
4. MongoDB-backed memory with caching
5. OFF-TOPIC DETECTION AND SMART REDIRECT ✅ NEW
"""

from typing import TypedDict, List, Optional
import os

# LangSmith Configuration - Monitoring and tracing enabled
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "bayai-chatbot")

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .llm import llm
from .rag import search_kb, get_relevant_sources
from .web_search import search_web, get_web_sources
from .quick_responses import get_quick_response, needs_quick_response
from .prompts import MAIN_SYSTEM_PROMPT, FALLBACK_MESSAGE, CONVERSATION_AWARE_PROMPT
from .query_rewriter import rewrite_query, should_rewrite_query
from .summarizer import get_summarized_context, format_context_with_summary
from .off_topic_handler import (
    detect_off_topic,
    generate_redirect_response,
    should_check_off_topic,
    is_greeting
)
# 🆕 Import new modules for lead collection
from .intent_detector import detect_intent, get_intent_specific_guidance, UserIntent
from .conversation_state import analyze_conversation_state, ConversationStage
from .entity_extractor import extract_contact_info, get_missing_contact_fields

# ---------- Helper Functions ----------

def clean_response_formatting(text: str) -> str:
    """
    Minimal cleanup - LLM controls formatting and structure.
    Only removes excessive whitespace, preserves LLM's natural flow.

    Args:
        text: Raw response text from LLM

    Returns:
        Cleaned text (LLM-controlled structure preserved)
    """
    import re

    # Just basic cleanup - preserve LLM's structure
    text = text.strip()

    # Remove excessive newlines (more than 2) but keep LLM's line breaks
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove excessive spaces
    text = re.sub(r' {2,}', ' ', text)

    # Clean up spaces before punctuation
    text = re.sub(r'\s+([.,!?])', r'\1', text)

    print(f"[FORMATTING] Cleaned: {len(text)} chars (LLM structure preserved)")

    return text

# ---------- State Definition ----------

class ChatState(TypedDict):
    session_id: str
    question: str
    original_question: str
    namespace: str
    chat_history: List[BaseMessage]
    conversation_summary: str
    recent_messages: List[BaseMessage]
    context: str
    answer: str
    sources: List[dict]
    company_name: str
    use_web_search: bool
    skip_search: bool
    rewritten_query: bool
    is_off_topic: bool  # Track if question is off-topic
    off_topic_redirect: bool  # Flag for redirect response
    # 🆕 Lead Collection Fields
    detected_intent: str  # User's intent (greeting, question, callback_request, etc.)
    conversation_stage: str  # Current conversation stage
    collected_contact: dict  # Collected contact info: {name, phone, email}
    needs_callback: bool  # Whether user requested callback
    contact_confirmed: bool  # Whether contact info was confirmed

# ---------- Nodes ----------

def classify_node(state: ChatState):
    """
    Classify the question, detect intent, extract contact info, and handle quick responses.
    🆕 Now includes lead collection capabilities!
    """
    print(f"\n[LANGGRAPH] === CLASSIFY NODE ===")
    print(f"[LANGGRAPH] Question: {state['question']}")

    # Store original question
    state["original_question"] = state["question"]
    state["is_off_topic"] = False
    state["off_topic_redirect"] = False

    # 🆕 Detect user intent
    intent, confidence = detect_intent(state["question"], state.get("chat_history", []))
    state["detected_intent"] = intent.value
    print(f"[LANGGRAPH] 🎯 Detected intent: {intent.value} (confidence: {confidence:.2f})")

    # 🆕 Analyze conversation state
    conv_state = analyze_conversation_state(state.get("chat_history", []), state["question"])
    state["conversation_stage"] = conv_state.stage.value
    state["needs_callback"] = conv_state.needs_callback
    state["contact_confirmed"] = conv_state.callback_confirmed
    print(f"[LANGGRAPH] 📊 Conversation stage: {conv_state.stage.value}")

    # 🆕 Extract contact information automatically
    extracted_info = extract_contact_info(state["question"], state.get("chat_history", []))

    # Initialize or update collected contact info
    if "collected_contact" not in state or state["collected_contact"] is None:
        state["collected_contact"] = {"name": None, "phone": None, "email": None}

    # Update with any newly extracted info
    if extracted_info["name"]:
        state["collected_contact"]["name"] = extracted_info["name"]
        print(f"[LANGGRAPH] 👤 Extracted name: {extracted_info['name']}")
    if extracted_info["phone"]:
        state["collected_contact"]["phone"] = extracted_info["phone"]
        print(f"[LANGGRAPH] 📞 Extracted phone: {extracted_info['phone']}")
    if extracted_info["email"]:
        state["collected_contact"]["email"] = extracted_info["email"]
        print(f"[LANGGRAPH] 📧 Extracted email: {extracted_info['email']}")

    # Show what contact info we still need
    if state["needs_callback"]:
        missing_fields = get_missing_contact_fields(state["collected_contact"], required_fields=['name', 'phone'])
        if missing_fields:
            print(f"[LANGGRAPH] ⚠️ Missing contact info: {', '.join(missing_fields)}")
        else:
            print(f"[LANGGRAPH] ✅ Complete contact info collected!")

    # Check if this is a quick response scenario
    quick_answer = get_quick_response(
        text=state["question"],
        company_name=state.get("company_name", "our company"),
        chat_history=state.get("chat_history", []),
        has_kb_data=True
    )

    if quick_answer:
        print(f"[LANGGRAPH] ✓ Quick response detected")
        state["answer"] = clean_response_formatting(quick_answer)
        state["context"] = "Quick response - no search needed"
        state["sources"] = []
        state["skip_search"] = True
        state["use_web_search"] = False
        state["rewritten_query"] = False
    else:
        print(f"[LANGGRAPH] → Needs full processing")
        state["skip_search"] = False
        state["rewritten_query"] = False

    return state

def rewrite_node(state: ChatState):
    """
    Rewrite query to be standalone using conversation context.
    This ensures vector search works correctly with pronouns and context-dependent queries.
    """
    print(f"\n[LANGGRAPH] === REWRITE NODE ===")

    question = state["question"]
    chat_history = state.get("chat_history", [])

    # Check if rewriting is needed
    if should_rewrite_query(question, chat_history):
        print(f"[LANGGRAPH] Query needs rewriting")
        rewritten = rewrite_query(question, chat_history)

        if rewritten != question:
            print(f"[LANGGRAPH] Original: {question}")
            print(f"[LANGGRAPH] Rewritten: {rewritten}")
            state["question"] = rewritten
            state["rewritten_query"] = True
        else:
            print(f"[LANGGRAPH] No rewriting performed")
            state["rewritten_query"] = False
    else:
        print(f"[LANGGRAPH] No rewriting needed")
        state["rewritten_query"] = False

    return state

def retrieve_node(state: ChatState):
    """Retrieve relevant context from knowledge base"""
    print(f"\n[LANGGRAPH] === RETRIEVE NODE ===")
    print(f"[LANGGRAPH] Session: {state['session_id']}")
    print(f"[LANGGRAPH] Question: {state['question']}")
    print(f"[LANGGRAPH] Namespace: {state['namespace']}")

    # Use rewritten query for search if available
    search_query = state["question"]
    print(f"[LANGGRAPH] Search query: {search_query}")

    # Search knowledge base for relevant context
    context = search_kb(search_query, state["namespace"])
    state["context"] = context

    # Get sources for citations
    sources = get_relevant_sources(search_query, state["namespace"])
    state["sources"] = sources

    print(f"[LANGGRAPH] Context found: {len(context)} characters")
    print(f"[LANGGRAPH] Sources found: {len(sources)} sources")

    # ✅ Check if this might be off-topic (BEFORE deciding on web search)
    original_question = state.get("original_question", state["question"])

    # If KB has poor results, check for off-topic
    if should_check_off_topic(original_question, context, sources):
        print(f"[LANGGRAPH] ⚠️ Possible off-topic question, checking...")

        is_off_topic, confidence = detect_off_topic(
            question=original_question,
            context=context if context else "",  # Pass empty string if no context
            company_name=state.get("company_name", "our company"),
            chat_history=state.get("chat_history", [])
        )

        print(f"[LANGGRAPH] Off-topic detection result: is_off_topic={is_off_topic}, confidence={confidence}")

        if is_off_topic and confidence > 0.7:
            print(f"[LANGGRAPH] 🚫 Off-topic detected (confidence: {confidence})")
            state["is_off_topic"] = True
            state["off_topic_redirect"] = True
            # Skip web search for off-topic
            state["use_web_search"] = False
            return state

    # Determine if we need web search (only if on-topic and KB insufficient)
    if not context or len(context.strip()) < 50:
        print(f"[LANGGRAPH] ⚠️ Insufficient KB data - will use web search")
        state["use_web_search"] = True
    else:
        state["use_web_search"] = False

    return state

def web_search_node(state: ChatState):
    """Search the web when KB has no relevant data"""
    print(f"\n[LANGGRAPH] === WEB SEARCH NODE ===")

    # Use original question for web search (not rewritten)
    search_question = state.get("original_question", state["question"])

    # Perform web search
    web_answer = search_web(
        search_question,
        state.get("company_name", "our company"),
        state.get("chat_history", [])
    )
    state["context"] = web_answer

    # Get web sources
    web_sources = get_web_sources(search_question)
    state["sources"] = web_sources

    print(f"[LANGGRAPH] Web search completed")

    return state

def off_topic_redirect_node(state: ChatState):
    """
    ✅ NEW NODE: Generate smart redirect for off-topic questions
    """
    print(f"\n[LANGGRAPH] === OFF-TOPIC REDIRECT NODE ===")

    original_question = state.get("original_question", state["question"])

    # Generate redirect response
    redirect_response = generate_redirect_response(
        question=original_question,
        context=state.get("context", ""),
        company_name=state.get("company_name", "our company"),
        chat_history=state.get("chat_history", [])
    )

    # Clean up formatting for better user experience
    state["answer"] = clean_response_formatting(redirect_response)
    state["sources"] = []  # No sources for redirect

    print(f"[LANGGRAPH] Redirect response generated")

    return state

def should_skip_search(state: ChatState) -> str:
    """Routing function after classification"""
    if state.get("skip_search", False):
        return "end"  # Skip directly to end for quick responses
    else:
        return "rewrite"  # Go to rewrite node first

def should_redirect_off_topic(state: ChatState) -> str:
    """
    ✅ NEW: Routing function after retrieval to check for off-topic
    """
    if state.get("off_topic_redirect", False):
        return "off_topic_redirect"  # Redirect off-topic questions
    elif state.get("use_web_search", False):
        return "web_search"  # Use web search if KB insufficient
    else:
        return "answer"  # Generate answer from KB

def format_chat_history_with_summary(
    conversation_summary: str,
    recent_messages: List[BaseMessage],
    max_recent: int = 6
) -> str:
    """
    Format chat history using summary + recent messages.

    Args:
        conversation_summary: Summary of older conversation
        recent_messages: Recent conversation messages
        max_recent: Maximum recent messages to include

    Returns:
        Formatted conversation context
    """
    parts = []

    # Add summary if exists
    if conversation_summary:
        parts.append("=== Previous Context ===")
        parts.append(conversation_summary)
        parts.append("")

    # Add recent messages
    if recent_messages:
        if conversation_summary:
            parts.append("=== Recent Conversation ===")

        formatted_messages = []
        for msg in recent_messages[-max_recent:]:
            if isinstance(msg, HumanMessage):
                formatted_messages.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"Assistant: {msg.content}")

        parts.append("\n".join(formatted_messages))

    return "\n".join(parts) if parts else "No previous conversation"

def answer_node(state: ChatState):
    """
    Generate answer using LLM with context (KB + web search if available).
    🆕 Now includes dynamic guidance based on intent and contact collection status!
    """
    print(f"\n[LANGGRAPH] === ANSWER NODE ===")

    # If no context at all
    if not state["context"]:
        print(f"[LANGGRAPH] No context available - using fallback")
        state["answer"] = FALLBACK_MESSAGE
        return state

    # Note: At this point, context is either from KB or web search
    # The LLM will use whatever context is available to create a natural response

    # Get conversation context with summarization
    chat_history = state.get("chat_history", [])
    conversation_summary = state.get("conversation_summary", "")
    recent_messages = state.get("recent_messages", chat_history)

    # Format conversation context
    history_text = format_chat_history_with_summary(
        conversation_summary,
        recent_messages,
        max_recent=6
    )

    company_name = state.get("company_name", "our company")
    response_question = state.get("original_question", state["question"])
    is_from_web = state.get("use_web_search", False)

    # 🆕 Build dynamic guidance based on intent and contact collection
    dynamic_guidance = ""

    # Add intent-specific guidance
    if state.get("detected_intent"):
        intent_guidance = get_intent_specific_guidance(UserIntent(state["detected_intent"]))
        if intent_guidance:
            dynamic_guidance += f"\n\n🎯 INTENT GUIDANCE: {intent_guidance}"

    # 🆕 Check if user declined callback in conversation history
    user_declined_callback = False
    if chat_history:
        # Check last few messages for decline patterns
        recent_messages = chat_history[-6:] if len(chat_history) >= 6 else chat_history
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                msg_lower = msg.content.lower()
                decline_patterns = [
                    'no thanks', 'not interested', "don't call", "dont call",
                    "i'm not interested", "im not interested", 'no thank you',
                    'not now', 'maybe later', 'no need'
                ]
                if any(pattern in msg_lower for pattern in decline_patterns):
                    user_declined_callback = True
                    break

    # Add contact collection status
    if state.get("needs_callback"):
        collected = state.get("collected_contact", {})
        missing = get_missing_contact_fields(collected, required_fields=['name', 'phone'])

        # 🆕 Check if user declined
        if user_declined_callback:
            dynamic_guidance += f"\n\n🚫 USER DECLINED CALLBACK:"
            dynamic_guidance += f"\n- User said they're NOT interested earlier"
            dynamic_guidance += f"\n- DON'T ask for contact info again"
            dynamic_guidance += f"\n- DO offer other help instead"
        elif missing:
            dynamic_guidance += f"\n\n📋 CONTACT COLLECTION STATUS:"
            # Show what we already have
            collected_items = [k for k, v in collected.items() if v]
            if collected_items:
                dynamic_guidance += f"\n- ✅ Already have: {', '.join(collected_items)}"
                # Show the actual values
                for item in collected_items:
                    dynamic_guidance += f"\n  • {item.title()}: {collected[item]}"
            dynamic_guidance += f"\n- ⚠️ Still need: {', '.join(missing)}"
            dynamic_guidance += f"\n- ❗ DON'T ask for info you already have!"
            dynamic_guidance += f"\n- Next: Ask ONLY for {missing[0]} (ask once, don't repeat)"
        else:
            # All contact info collected!
            name = collected.get('name', 'Unknown')
            phone = collected.get('phone', 'Unknown')
            dynamic_guidance += f"\n\n✅ CONTACT INFO COMPLETE:"
            dynamic_guidance += f"\n- Name: {name}"
            dynamic_guidance += f"\n- Phone: {phone}"
            dynamic_guidance += f"\n- ❗ DON'T ask for name or phone again - you have both!"
            if not state.get("contact_confirmed"):
                dynamic_guidance += f"\n- Action: Confirm these details ONCE, then move on"
            else:
                dynamic_guidance += f"\n- Action: Thank them, confirm someone will call"

    # Add conversation stage context
    if state.get("conversation_stage"):
        dynamic_guidance += f"\n\n📍 STAGE: {state['conversation_stage']}"

    print(f"[LANGGRAPH] Generating answer")
    print(f"[LANGGRAPH] Company: {company_name}")
    print(f"[LANGGRAPH] Context source: {'Web Search' if is_from_web else 'Knowledge Base'}")
    print(f"[LANGGRAPH] Has conversation history: {bool(chat_history or conversation_summary)}")

    try:
        # Always use LLM to create natural, human-like responses
        if chat_history or conversation_summary:
            # With conversation history - be contextually aware
            # 🆕 Add dynamic guidance to system prompt
            enhanced_prompt = CONVERSATION_AWARE_PROMPT + dynamic_guidance

            prompt = ChatPromptTemplate.from_messages([
                ("system", enhanced_prompt),
                ("human", "Question: {question}")
            ])

            chain = prompt | llm | StrOutputParser()

            answer = chain.invoke({
                "company_name": company_name,
                "chat_history": history_text,
                "question": response_question,
                "context": state["context"]
            })
        else:
            # First message - use simple prompt
            # 🆕 Add dynamic guidance to system prompt
            enhanced_prompt = MAIN_SYSTEM_PROMPT + dynamic_guidance

            prompt = ChatPromptTemplate.from_messages([
                ("system", enhanced_prompt),
                ("human", "Question: {question}")
            ])

            chain = prompt | llm | StrOutputParser()

            answer = chain.invoke({
                "company_name": company_name,
                "context": state["context"],
                "question": response_question
            })

        # Clean up formatting - keep it natural
        state["answer"] = clean_response_formatting(answer)
        print(f"[LANGGRAPH] ✅ Answer generated: {len(state['answer'])} characters")

        # 🆕 Log collected contact info if available
        if state.get("collected_contact"):
            collected = state["collected_contact"]
            if any(collected.values()):
                print(f"[LANGGRAPH] 📋 Lead Info - Name: {collected.get('name', 'N/A')}, Phone: {collected.get('phone', 'N/A')}, Email: {collected.get('email', 'N/A')}")
    except Exception as e:
        print(f"[LANGGRAPH] ❌ Error generating answer: {e}")
        state["answer"] = FALLBACK_MESSAGE

    return state

# ---------- Graph Construction ----------

def create_graph():
    """Create and compile the enhanced LangGraph workflow with off-topic detection"""
    graph = StateGraph(ChatState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("off_topic_redirect", off_topic_redirect_node)  # ✅ NEW
    graph.add_node("web_search", web_search_node)
    graph.add_node("answer", answer_node)

    # Define flow with conditional routing
    graph.set_entry_point("classify")

    # After classify: quick response (skip) or rewrite query
    graph.add_conditional_edges(
        "classify",
        should_skip_search,
        {
            "end": END,  # Quick responses skip to end
            "rewrite": "rewrite"  # Rewrite query before retrieval
        }
    )

    # After rewrite, go to retrieve
    graph.add_edge("rewrite", "retrieve")

    # ✅ NEW: After retrieve, check for off-topic, web search, or answer
    graph.add_conditional_edges(
        "retrieve",
        should_redirect_off_topic,
        {
            "off_topic_redirect": "off_topic_redirect",  # ✅ NEW: Redirect off-topic
            "web_search": "web_search",
            "answer": "answer"
        }
    )

    # ✅ NEW: Off-topic redirect goes to END
    graph.add_edge("off_topic_redirect", END)

    # After web search, go to answer node
    graph.add_edge("web_search", "answer")

    # Answer node goes to END
    graph.add_edge("answer", END)

    return graph.compile()

# Create the compiled graph
app = create_graph()
