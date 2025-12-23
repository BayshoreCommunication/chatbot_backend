from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .llm import llm
from .rag import search_kb, get_relevant_sources
from .web_search import search_web, get_web_sources
from .quick_responses import get_quick_response, needs_quick_response
from .prompts import MAIN_SYSTEM_PROMPT, FALLBACK_MESSAGE, CONVERSATION_AWARE_PROMPT

class ChatState(TypedDict):
    session_id: str
    question: str
    namespace: str
    chat_history: List[BaseMessage]
    context: str
    answer: str
    sources: List[dict]
    company_name: str
    use_web_search: bool  # Flag to track if web search is needed
    skip_search: bool  # Flag to skip search for quick responses

# ---------- Nodes ----------

def classify_node(state: ChatState):
    """Classify the question and handle quick responses"""
    print(f"\n[LANGGRAPH] === CLASSIFY NODE ===")
    print(f"[LANGGRAPH] Question: {state['question']}")
    
    # Check if this is a quick response scenario
    quick_answer = get_quick_response(
        text=state["question"],
        company_name=state.get("company_name", "our company"),
        chat_history=state.get("chat_history", []),
        has_kb_data=True  # We'll update this based on KB availability
    )
    
    if quick_answer:
        print(f"[LANGGRAPH] ✓ Quick response detected")
        state["answer"] = quick_answer
        state["context"] = "Quick response - no search needed"
        state["sources"] = []
        state["skip_search"] = True
        state["use_web_search"] = False
    else:
        print(f"[LANGGRAPH] → Needs full processing")
        state["skip_search"] = False
    
    return state

def retrieve_node(state: ChatState):
    """Retrieve relevant context from knowledge base"""
    print(f"\n[LANGGRAPH] === RETRIEVE NODE ===")
    print(f"[LANGGRAPH] Session: {state['session_id']}")
    print(f"[LANGGRAPH] Question: {state['question']}")
    print(f"[LANGGRAPH] Namespace: {state['namespace']}")
    
    # Search knowledge base for relevant context
    context = search_kb(state["question"], state["namespace"])
    state["context"] = context
    
    # Get sources for citations
    sources = get_relevant_sources(state["question"], state["namespace"])
    state["sources"] = sources
    
    print(f"[LANGGRAPH] Context found: {len(context)} characters")
    print(f"[LANGGRAPH] Sources found: {len(sources)} sources")
    
    # Determine if we need web search
    if not context or len(context.strip()) < 50:
        print(f"[LANGGRAPH] ⚠️ Insufficient KB data - will use web search")
        state["use_web_search"] = True
    else:
        state["use_web_search"] = False
    
    return state

def web_search_node(state: ChatState):
    """Search the web when KB has no relevant data"""
    print(f"\n[LANGGRAPH] === WEB SEARCH NODE ===")
    
    # Perform web search
    web_answer = search_web(
        state["question"], 
        state.get("company_name", "our company"),
        state.get("chat_history", [])
    )
    state["context"] = web_answer  # Use web answer as context
    
    # Get web sources
    web_sources = get_web_sources(state["question"])
    state["sources"] = web_sources
    
    print(f"[LANGGRAPH] Web search completed")
    
    return state

def should_skip_search(state: ChatState) -> str:
    """Routing function after classification"""
    if state.get("skip_search", False):
        return "end"  # Skip directly to end for quick responses
    else:
        return "retrieve"  # Continue to KB search

def should_use_web_search(state: ChatState) -> str:
    """Routing function to decide between KB answer or web search"""
    if state.get("use_web_search", False):
        return "web_search"
    else:
        return "answer"

def format_chat_history(chat_history: List[BaseMessage]) -> str:
    """Format chat history for prompt"""
    if not chat_history:
        return "No previous conversation"
    
    formatted = []
    for msg in chat_history[-6:]:  # Last 6 messages (3 turns)
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            formatted.append(f"Assistant: {msg.content}")
    
    return "\n".join(formatted)

def answer_node(state: ChatState):
    """Generate answer using LLM with context"""
    print(f"\n[LANGGRAPH] === ANSWER NODE ===")
    
    # Check if this is from web search
    is_web_search = state.get("use_web_search", False)
    
    if is_web_search:
        # If from web search, context is already the answer
        print(f"[LANGGRAPH] Using web search answer")
        state["answer"] = state["context"]
        return state
    
    # If no context found from KB (shouldn't happen due to routing, but safe check)
    if not state["context"]:
        print(f"[LANGGRAPH] No context available - using fallback")
        state["answer"] = FALLBACK_MESSAGE
        return state

    # Format chat history
    history_text = format_chat_history(state["chat_history"])
    company_name = state.get("company_name", "our company")
    
    print(f"[LANGGRAPH] Generating answer with KB context and history")
    print(f"[LANGGRAPH] Company: {company_name}")
    
    # Create prompt with conversation awareness
    if state["chat_history"]:
        # Use conversation-aware prompt when history exists
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI assistant representing {company_name}."),
            ("human", CONVERSATION_AWARE_PROMPT)
        ])
        
        chain = prompt | llm | StrOutputParser()
        
        answer = chain.invoke({
            "company_name": company_name,
            "chat_history": history_text,
            "question": state["question"],
            "context": state["context"]
        })
    else:
        # Use simple prompt for first message
        prompt = ChatPromptTemplate.from_messages([
            ("system", MAIN_SYSTEM_PROMPT),
            ("human", "Question: {question}")
        ])
        
        chain = prompt | llm | StrOutputParser()
        
        answer = chain.invoke({
            "company_name": company_name,
            "context": state["context"],
            "question": state["question"]
        })
    
    state["answer"] = answer
    print(f"[LANGGRAPH] Answer generated: {len(answer)} characters")
    
    return state

# ---------- Graph Construction ----------

def create_graph():
    """Create and compile the LangGraph workflow with quick responses and conditional web search"""
    graph = StateGraph(ChatState)
    
    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("answer", answer_node)
    
    # Define flow with conditional routing
    graph.set_entry_point("classify")
    
    # After classify, decide: quick response (skip) or full processing (retrieve)
    graph.add_conditional_edges(
        "classify",
        should_skip_search,
        {
            "end": END,  # Quick responses skip to end
            "retrieve": "retrieve"  # Normal questions go to KB search
        }
    )
    
    # After retrieve, decide: KB answer or web search
    graph.add_conditional_edges(
        "retrieve",
        should_use_web_search,
        {
            "web_search": "web_search",
            "answer": "answer"
        }
    )
    
    # After web search, go to answer node
    graph.add_edge("web_search", "answer")
    
    # Answer node goes to END
    graph.add_edge("answer", END)
    
    return graph.compile()

# Create the compiled graph
app = create_graph()
