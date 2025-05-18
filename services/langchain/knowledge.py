import openai
import json

def search_knowledge_base(query, vectorstore, user_info):
    """Search the knowledge base for relevant information"""
    if vectorstore is None:
        print("WARNING: vectorstore is None, cannot perform knowledge search")
        return "", {}
    
    try:
        # Create a more specific query to search for user information if that seems to be what they're asking
        search_query = query
        
        # If the query is about the AI's identity, modify the search term to find bot information
        identity_keywords = ["who are you", "what are you", "your name", "about yourself", "tell me about you"]
        
        # Keywords that might be asking about personal experience or background
        experience_keywords = ["your experience", "your background", "your education", "your skills", 
                              "your work", "your expertise", "about your experience", "qualification", 
                              "tell me about your work", "your profile", "about your background"]
        
        # Check for identity questions
        is_identity_query = any(keyword in query.lower() for keyword in identity_keywords)
        # Check for experience/background questions
        is_experience_query = any(keyword in query.lower() for keyword in experience_keywords)
        
        print(f"Query analysis - Identity query: {is_identity_query}, Experience query: {is_experience_query}")
        
        # Modify search query based on query type
        if is_identity_query:
            search_query = "AI assistant information identity description"
            print(f"Modified search query for identity: '{search_query}'")
        elif is_experience_query:
            search_query = "Rayhan lawyer profile experience background education"
            print(f"Modified search query for experience: '{search_query}'")
        
        # If the query may be about the user, create a secondary search specific to user data
        user_related_keywords = ["my information", "about me", "my profile", "my data", "my account"]
        user_search_needed = any(keyword in query.lower() for keyword in user_related_keywords) or (user_info["name"].lower() != "unknown" and user_info["name"].lower() in query.lower())
        
        # Initialize variables
        retrieved_context = ""
        personal_information = {}
        
        # Perform primary vector search with the appropriate query
        try:
            print(f"Executing vector search with query: '{search_query}'")
            # Try with a higher k value to increase chances of finding relevant info
            docs = vectorstore.similarity_search(search_query, k=5)
            print(f"Found {len(docs)} documents in similarity search")
            
            if len(docs) > 0:
                # Print document IDs for debugging
                doc_ids = [doc.metadata.get('id', 'unknown') for doc in docs]
                print(f"Document IDs: {doc_ids}")
                
                # Join document contents
                retrieved_context = "\n\n".join([doc.page_content for doc in docs])
                print(f"Retrieved context: {retrieved_context[:200]}...")
            else:
                print("WARNING: No documents returned from vector search")
                # Try a more general search if specific query returned nothing
                if is_experience_query:
                    # Try a more direct search for resume info
                    generic_search_query = "Rayhan resume CV lawyer"
                else:
                    generic_search_query = "general information"
                    
                print(f"Trying generic search with: '{generic_search_query}'")
                docs = vectorstore.similarity_search(generic_search_query, k=5)
                if len(docs) > 0:
                    print(f"Found {len(docs)} documents in generic search")
                    retrieved_context = "\n\n".join([doc.page_content for doc in docs])
                    print(f"Retrieved context from generic search: {retrieved_context[:200]}...")
                else:
                    print("ERROR: Even generic search returned no documents")
        except Exception as e:
            print(f"Error in primary vector search: {str(e)}")
            retrieved_context = "Unable to retrieve information from knowledge base."
        
        # If query might be about user, do a second search with user's name
        if user_search_needed:
            try:
                user_docs = vectorstore.similarity_search(f"information about {user_info['name']}", k=2)
                user_context = "\n\n".join([doc.page_content for doc in user_docs])
                
                # Extract structured personal information if found
                if user_context:
                    personal_information = extract_personal_information(user_context)
            except Exception as e:
                print(f"Error in secondary vector search: {str(e)}")
        
        # Special handling for experience queries when they don't return good results
        if is_experience_query and (not retrieved_context or len(retrieved_context) < 100):
            print("Attempting direct document retrieval for experience query")
            try:
                # Try a completely different search approach for experience
                experience_docs = vectorstore.similarity_search("Rayhan Al Mim lawyer resume", k=3)
                if experience_docs:
                    experience_context = "\n\n".join([doc.page_content for doc in experience_docs])
                    # Only use this if it's substantial and different from what we already have
                    if len(experience_context) > 100 and experience_context != retrieved_context:
                        print("Found better experience context through direct search")
                        retrieved_context = experience_context
            except Exception as e:
                print(f"Error in experience fallback search: {str(e)}")
        
        # If the query is about AI identity and we didn't find good info, add clarification
        if is_identity_query and "AI" not in retrieved_context:
            retrieved_context += "\n\nClarification: This is an AI assistant, not a human. The AI's purpose is to help users with information, schedule appointments, and answer questions. The AI does not have personal information and should not claim to be any specific person."
        
        return retrieved_context, personal_information
    except Exception as e:
        print(f"Error retrieving from vector store: {str(e)}")
        return "No relevant information found in knowledge base.", {}

def extract_personal_information(user_context):
    """Extract structured personal information from user context"""
    personal_information_prompt = f"""
    Extract structured personal information from this document about a person.
    
    DOCUMENT: {user_context}
    
    Extract information in this JSON format:
    {{
        "full_name": "Person's full name or null if not found",
        "role": "Person's role/job title or null if not found",
        "organization": "Person's organization or null if not found",
        "bio": "Short bio summary or null if not found",
        "is_ai": false
    }}
    """
    
    try:
        personal_info_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": personal_information_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        personal_information = json.loads(personal_info_response.choices[0].message.content)
        print(f"Extracted personal information: {personal_information}")
        return personal_information
    except Exception as e:
        print(f"Error extracting personal information: {str(e)}")
        return {} 