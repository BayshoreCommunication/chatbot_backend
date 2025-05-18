from langchain_openai import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from dotenv import load_dotenv
import os
import openai

from services.language_detect import detect_language
from services.notification import send_email_notification
import json

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

def initialize():
    """Initialize all components of the langchain engine"""
    global llm, embeddings, pc, index_name, vectorstore, qa_chain, prompt_templates, chains
    
    print("Initializing langchain engine components...")
    
    # Initialize OpenAI
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo", 
        temperature=0.5,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base="https://api.openai.com/v1"
    )
    print("LLM initialized")
    
    # Initialize embeddings
    embeddings = initialize_embeddings()
    print("Embeddings initialized")
    
    # Initialize vector store
    pc, index_name, vectorstore = initialize_vectorstore(embeddings)
    if vectorstore:
        print(f"Vectorstore initialized successfully with index: {index_name}")
        # Verify it works by testing a simple query
        try:
            test_docs = vectorstore.similarity_search("test", k=1)
            print(f"Vectorstore test query found {len(test_docs)} documents")
        except Exception as e:
            print(f"WARNING: Vectorstore test query failed: {str(e)}")
    else:
        print("WARNING: Vectorstore initialization failed")
    
    # Set up QA chain
    qa_chain = load_qa_chain(llm, chain_type="stuff")
    print("QA chain initialized")
    
    # Initialize prompt templates and chains
    prompt_templates = initialize_prompt_templates()
    chains = initialize_chains(llm)
    print("Prompts and chains initialized")
    
    print("Langchain engine initialization complete")

# Initialize the engine when this module is imported
try:
    print("Starting langchain engine initialization...")
    initialize()
    print("Langchain engine initialization completed successfully")
except Exception as e:
    print(f"ERROR during langchain engine initialization: {str(e)}")
    print("Some features may not be available")

@create_error_handler
def ask_bot(query: str, mode="faq", user_data=None, available_slots=None, session_id=None):
    """Process user query using a central AI-driven approach"""
    # Initialize user data if None
    if user_data is None:
        user_data = {}
    
    # Detect language
    language = detect_language(query)
    
    # Record conversation history if not present in user_data
    if "conversation_history" not in user_data:
        user_data["conversation_history"] = []
    
    # Append current query to history
    user_data["conversation_history"].append({"role": "user", "content": query})
    
    # Create a comprehensive context for the AI to analyze
    has_booked_appointment = "appointment_slot" in user_data and user_data["appointment_slot"]
    needs_info = "name" not in user_data or "email" not in user_data
    has_vector_data = vectorstore is not None
    
    # Get available slots if in appointment context
    if mode == "appointment" and not available_slots:
        available_slots = get_available_slots()
    
    # Extract relevant information from user_data
    user_info = {
        "name": user_data.get("name", "Unknown"),
        "email": user_data.get("email", "Unknown"),
        "has_appointment": has_booked_appointment,
        "appointment_details": user_data.get("appointment_slot", "None")
    }
    
    # Extract past few conversation turns for context
    conversation_context = user_data["conversation_history"][-5:] if len(user_data["conversation_history"]) > 0 else []
    conversation_summary = "\n".join([f"{'User' if msg['role'] == 'user' else 'AI'}: {msg['content']}" for msg in conversation_context])
    
    # STEP 1: Analyze the query to determine intent and appropriate mode
    analysis = analyze_query(query, user_info, mode, needs_info, has_vector_data, conversation_summary)
    
    # STEP 2: Handle Information Collection if needed
    if analysis["collect_info"] and analysis["info_to_collect"] != "none":
        info_type = analysis["info_to_collect"]
        
        # Handle name collection
        if info_type == "name" and "name" not in user_data:
            return handle_name_collection(query, user_data, analysis["appropriate_mode"], language)
        
        # Handle email collection
        elif info_type == "email" and "email" not in user_data:
            return handle_email_collection(query, user_data, analysis["appropriate_mode"], language)
    
    # STEP 3: Handle Appointment Actions if needed
    if analysis["appropriate_mode"] == "appointment" and analysis["appointment_action"] != "none":
        action = analysis["appointment_action"]
        
        # Handle appointment booking
        if action == "book" and not has_booked_appointment:
            return handle_booking(query, user_data, available_slots, language)
        
        # Handle appointment rescheduling
        elif action == "reschedule" and has_booked_appointment:
            return handle_rescheduling(user_data, available_slots, language)
        
        # Handle appointment cancellation
        elif action == "cancel" and has_booked_appointment:
            return handle_cancellation(user_data, language)
        
        # Handle appointment information request
        elif action == "info" and has_booked_appointment:
            return handle_appointment_info(user_data, language)
    
    # STEP 4: Knowledge Base Lookup if needed
    retrieved_context = ""
    personal_information = {}
    if analysis["needs_knowledge_lookup"] and vectorstore is not None:
        retrieved_context, personal_information = search_knowledge_base(query, vectorstore, user_info)
    
    # STEP 5: Handle special cases if needed
    if analysis["special_handling"] == "identity":
        response = "I'm an AI assistant designed to help you with information, schedule appointments, and answer your questions. How can I assist you today?"
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": response
        })
        
        return {
            "answer": response,
            "mode": "faq",
            "language": language,
            "user_data": user_data
        }
    
    # STEP 6: Generate the final response
    final_response = generate_response(
        query, 
        user_info, 
        conversation_summary, 
        retrieved_context, 
        personal_information, 
        analysis, 
        language
    )
    
    # Add this interaction to history
    user_data["conversation_history"].append({
        "role": "assistant", 
        "content": final_response
    })
    
    # Determine final mode for response
    final_mode = analysis["appropriate_mode"]
    # Reset to FAQ mode if we've completed other flows
    if has_booked_appointment and final_mode == "appointment":
        final_mode = "faq"
    
    return {
        "answer": final_response,
        "mode": final_mode,
        "language": language,
        "user_data": user_data
    }

def add_document(file_path=None, url=None, text=None):
    """Add documents to the vector store"""
    global llm, embeddings, pc, index_name, vectorstore, qa_chain, prompt_templates, chains
    
    # Call the vectorstore module function
    result = add_document_to_vectorstore(vectorstore, pc, index_name, embeddings, file_path, url, text)
    
    # If successful, update our global vectorstore instance
    if result["status"] == "success" and "vectorstore" in globals() and globals()["vectorstore"] is not None:
        vectorstore = globals()["vectorstore"]
        print(f"Updated global vectorstore instance")
    
    return result

def escalate_to_human(query, user_info):
    """Escalate a conversation to a human operator"""
    # Send notification to business owner
    send_email_notification(
        "Chat Escalation Required", 
        f"Query: {query}\nUser info: {json.dumps(user_info)}"
    )
    
    return {
        "status": "escalated",
        "message": "This conversation has been escalated to a human operator who will contact you shortly."
    }

# Re-export core components for other modules to use
def get_vectorstore():
    """Return the global vectorstore instance"""
    global vectorstore
    return vectorstore

def reinitialize_vectorstore():
    """Force reinitialization of the vectorstore"""
    global embeddings, pc, index_name, vectorstore
    
    print("Forcing vectorstore reinitialization")
    pc, index_name, vectorstore = initialize_vectorstore(embeddings)
    return vectorstore 