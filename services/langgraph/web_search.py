"""
Web search functionality for fallback when knowledge base has no relevant data.
"""

import os
from typing import List, Dict, Any
from openai import OpenAI
from langchain_core.messages import HumanMessage, AIMessage

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_web(query: str, company_name: str, chat_history: List = None) -> str:
    """
    Search the web when knowledge base has no relevant information.
    Uses GPT-4 with web search capabilities.
    
    Args:
        query: User's question
        company_name: Organization name to restrict search context
        chat_history: List of previous conversation messages
        
    Returns:
        Formatted answer from web search results
    """
    try:
        print(f"\n[WEB SEARCH] Query: {query}")
        print(f"[WEB SEARCH] Company: {company_name}")
        
        # Build messages list with history
        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful AI assistant for {company_name}.

The knowledge base had limited information, so blend your general knowledge with being helpful.

CONTACT INFO SHARING:
- You ARE part of {company_name} - share company contact information naturally
- If user asks for email, phone, address - share the organization's public contact details
- Say "You can reach us at..." / "Our email is..." / "My office number is..."
- NEVER refuse to share company contact information - you represent the company
- Only avoid sharing private individual contact info not related to the business

GREETING HANDLING:
- If user says "hi", "hello", "hey" → Greet warmly in their language, then offer to help
- Keep it SHORT and welcoming (2 sentences max)
- Example: "Hello! I'm here to help you. What can I assist you with today?"

GENERAL RESPONSES:
- Try to be helpful with your general knowledge
- Mention the type of service provided by {company_name}
- If you don't have specific info, offer to connect them with the team
- Always sound warm and service-oriented

STYLE:
- Keep responses SHORT (2-3 sentences max)
- Sound human and conversational
- Support any language the user speaks
- Be warm, simple, and helpful! 🎯"""
            }
        ]
        
        # Add conversation history if available
        if chat_history:
            print(f"[WEB SEARCH] Adding {len(chat_history)} messages from history")
            for msg in chat_history[-6:]:  # Last 6 messages (3 turns)
                if isinstance(msg, HumanMessage):
                    messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages.append({"role": "assistant", "content": msg.content})
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        # Use GPT with web search prompt
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.5,
            max_tokens=300
        )
        
        answer = response.choices[0].message.content.strip()
        print(f"[WEB SEARCH] ✅ Answer generated: {len(answer)} characters")
        
        return answer
        
    except Exception as e:
        print(f"[WEB SEARCH] ❌ Error: {e}")
        return (
            "I don't have specific information about that in our knowledge base.\n\n"
            "Would you like me to connect you with someone who can help?"
        )

def get_web_sources(query: str) -> List[Dict[str, Any]]:
    """
    Get source information for web search results.
    
    Returns:
        List of source dictionaries
    """
    return [
        {
            "title": "General Knowledge",
            "score": 0.0,
            "url": "",
            "content_preview": "Answer generated using general AI knowledge"
        }
    ]
