from langchain_openai import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from dotenv import load_dotenv
import os
import openai

from services.language_detect import detect_language
from services.notification import send_email_notification
from services.database import get_organization_by_api_key
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

# Dictionary to store organization-specific vectorstores
org_vectorstores = {}

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
    
    # Ensure we have a valid index name
    index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
    print(f"Using Pinecone index name: {index_name}")
    
    # Initialize vector store (global default instance)
    pc, index_name, vectorstore, _ = initialize_vectorstore(embeddings)
    if vectorstore:
        print(f"Default vectorstore initialized successfully with index: {index_name}")
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

def get_org_vectorstore(api_key):
    """Get organization-specific vectorstore or create if not exists"""
    global embeddings, org_vectorstores, pc, index_name
    
    # If no API key, return default vectorstore
    if not api_key:
        print("No API key provided, using default vectorstore")
        return vectorstore
    
    # Check if we already have a vectorstore for this organization
    if api_key in org_vectorstores and org_vectorstores[api_key] is not None:
        print(f"Using cached vectorstore for organization with API key: {api_key[:8]}...")
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
            index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
            
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
            # This helps with our namespace checking in knowledge.py
            if not hasattr(org_vectorstore, 'namespace'):
                setattr(org_vectorstore, 'namespace', namespace)
            
            # Test the vector store with a simple query
            try:
                test_docs = org_vectorstore.similarity_search("test", k=1)
                print(f"Test query for namespace {namespace} returned {len(test_docs)} docs")
            except Exception as e:
                print(f"Test query for namespace {namespace} failed: {str(e)}")
                
            # Cache the vectorstore for future use
            org_vectorstores[api_key] = org_vectorstore
            print(f"Successfully initialized vectorstore for organization with namespace: {namespace}")
            return org_vectorstore
        except Exception as e:
            print(f"Error creating Pinecone vector store: {str(e)}")
            return vectorstore
            
    except Exception as e:
        print(f"Error initializing vectorstore for organization: {str(e)}")
        return vectorstore

@create_error_handler
def ask_bot(query: str, mode="faq", user_data=None, available_slots=None, session_id=None, api_key=None):
    """Process user query using a central AI-driven approach"""
    # Initialize user data if None
    if user_data is None:
        user_data = {}
    
    # Get the appropriate vectorstore for this organization
    org_vectorstore = get_org_vectorstore(api_key)
    if not org_vectorstore and api_key:
        print(f"WARNING: Failed to get organization vectorstore for API key: {api_key[:8]}...")
        return {
            "status": "error",
            "message": "Unable to access organization's knowledge base. Please contact support."
        }
    
    # Get organization info if API key is provided
    organization = None
    if api_key:
        organization = get_organization_by_api_key(api_key)
        print(f"Using organization: {organization['name']} with namespace: {organization.get('pinecone_namespace')}")
    
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
    has_vector_data = org_vectorstore is not None
    
    # Get available slots if in appointment context
    if mode == "appointment" and not available_slots:
        # In a real implementation, you would fetch slots for the specific organization
        if organization:
            # You could fetch organization-specific slots here
            # For now, using the default implementation
            available_slots = get_available_slots()
        else:
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
    
    # STEP 0: If this is first message and we need user info, always collect name first
    is_first_message = len(user_data["conversation_history"]) <= 1
    if is_first_message and "name" not in user_data:
        # We're starting a new conversation - always ask for name first
        return handle_name_collection("", user_data, mode, language)
    
    # STEP 1: Analyze the query to determine intent and appropriate mode
    analysis = analyze_query(query, user_info, mode, needs_info, has_vector_data, conversation_summary)
    
    # STEP 2: Handle Information Collection if needed
    # If we still need information, prioritize collecting it
    if needs_info:
        if "name" not in user_data:
            # If the query could be a name introduction, try to extract it
            return handle_name_collection(query, user_data, analysis["appropriate_mode"], language)
        elif "email" not in user_data:
            # Otherwise try to get their email
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
    if analysis["needs_knowledge_lookup"] and org_vectorstore is not None:
        retrieved_context, personal_information = search_knowledge_base(query, org_vectorstore, user_info)
    
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
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": identity_response
        })
        
        return {
            "answer": identity_response,
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

def add_document(file_path=None, url=None, text=None, api_key=None):
    """Add documents to the vector store"""
    global llm, embeddings, pc, index_name, vectorstore, qa_chain, prompt_templates, chains, org_vectorstores
    
    # Ensure index_name is properly set
    if not index_name:
        index_name = os.getenv("PINECONE_INDEX", "bayshoreai")
        print(f"Setting default index_name: {index_name}")
    
    # Get the organization-specific vectorstore if API key is provided
    if api_key:
        # First make sure organization exists
        organization = get_organization_by_api_key(api_key)
        if not organization:
            return {
                "status": "error",
                "message": "Invalid API key. Organization not found."
            }
        
        namespace = organization.get('pinecone_namespace')
        print(f"Organization namespace for upload: {namespace}")
            
        # Get or create organization vectorstore
        org_vectorstore = get_org_vectorstore(api_key)
        if not org_vectorstore:
            return {
                "status": "error",
                "message": "Failed to initialize vector store for organization."
            }
        
        # Import here to avoid circular imports
        from services.langchain.vectorstore import add_document_to_vectorstore
        
        # Call the vectorstore module function with the organization's API key
        result = add_document_to_vectorstore(
            org_vectorstore, pc, index_name, embeddings, 
            api_key=api_key, file_path=file_path, url=url, text=text
        )
        
        # Verify the document was successfully uploaded by performing a test query
        if result.get("status") == "success":
            print(f"Document upload reported success with {result.get('documents_added', 0)} documents added")
            
            # Test retrieval directly to verify the document is accessible
            if text:
                # Extract a unique phrase from the text to search for
                unique_phrases = []
                if "TEST-DOC-" in text:
                    import re
                    matches = re.findall(r'TEST-DOC-[a-zA-Z0-9]+', text)
                    if matches:
                        unique_phrases.extend(matches)
                
                # If we found unique phrases, search for them
                if unique_phrases:
                    try:
                        print(f"Testing retrieval with unique phrases: {unique_phrases}")
                        for phrase in unique_phrases:
                            results = org_vectorstore.similarity_search(
                                phrase, 
                                k=1,
                                namespace=namespace
                            )
                            if results and len(results) > 0:
                                print(f"SUCCESS: Found uploaded content when searching for '{phrase}'")
                                print(f"Retrieved content: {results[0].page_content[:100]}...")
                            else:
                                print(f"WARNING: No results found when searching for '{phrase}'")
                    except Exception as e:
                        print(f"Error during test retrieval: {str(e)}")
            
            # If successful, update our organization vectorstore cache
            if api_key:
                # Re-initialize the vector store to ensure it's updated
                new_org_vectorstore = get_org_vectorstore(api_key)
                if new_org_vectorstore:
                    org_vectorstores[api_key] = new_org_vectorstore
                    print(f"Updated vectorstore for organization with API key: {api_key[:8]}...")
        
        return result
    else:
        # Use default vectorstore if no API key
        from services.langchain.vectorstore import add_document_to_vectorstore
        
        result = add_document_to_vectorstore(
            vectorstore, pc, index_name, embeddings, 
            file_path=file_path, url=url, text=text
        )
        
        # If successful, update our global vectorstore instance
        if result.get("status") == "success" and "vectorstore" in globals() and globals()["vectorstore"] is not None:
            vectorstore = globals()["vectorstore"]
            print(f"Updated global vectorstore instance")
        
        return result

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

def get_vectorstore():
    """Get the global vectorstore instance"""
    return vectorstore

def reinitialize_vectorstore():
    """Reinitialize the vectorstore"""
    global embeddings, pc, index_name, vectorstore
    pc, index_name, vectorstore, _ = initialize_vectorstore(embeddings)
    return vectorstore 