import openai
import json

def search_knowledge_base(query, vectorstore, user_info):
    """Search the knowledge base for relevant information"""
    if vectorstore is None:
        print("WARNING: vectorstore is None, cannot perform knowledge search")
        return "", {}
    
    try:
        # Log the namespace being used to confirm organization-specific search
        try:
            print(f"Vectorstore type: {type(vectorstore).__name__}")
            
            # Look for namespace in different attributes
            namespace = None
            if hasattr(vectorstore, '_namespace'):
                namespace = vectorstore._namespace
                print(f"Found namespace in _namespace: {namespace}")
            elif hasattr(vectorstore, 'namespace'):
                namespace = vectorstore.namespace
                print(f"Found namespace in namespace: {namespace}")
            elif hasattr(vectorstore, 'index') and hasattr(vectorstore.index, 'namespace'):
                namespace = vectorstore.index.namespace
                print(f"Found namespace in index.namespace: {namespace}")
            else:
                print("WARNING: Cannot determine namespace, may be using global namespace")
                
                # Last resort - check if any namespace was explicitly set
                for attr_name in dir(vectorstore):
                    if "namespace" in attr_name.lower() and not attr_name.startswith("__"):
                        value = getattr(vectorstore, attr_name)
                        print(f"Found potential namespace in {attr_name}: {value}")
                
            # Get configuration details
            if hasattr(vectorstore, 'index'):
                print(f"Index: {vectorstore.index}")
            if hasattr(vectorstore, 'embedding'):
                print(f"Embedding type: {type(vectorstore.embedding).__name__}")
            
            print(f"Search query: '{query}'")
            print(f"Using namespace: {namespace}")
        except Exception as e:
            print(f"Error checking namespace: {str(e)}")
        
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
        if is_identity_query or is_experience_query:
            # For identity questions, we want to find personal information about the person in uploaded documents
            search_query = "personal information profile bio resume about"
            print(f"Modified search query for identity/experience: '{search_query}'")
        
        # Also check for unique identifier queries
        unique_id_keywords = ["unique identifier", "unique id", "identifier", "id code", "test-doc"]
        is_unique_id_query = any(keyword in query.lower() for keyword in unique_id_keywords)
        if is_unique_id_query:
            search_query = "unique identifier test-doc"
            print(f"Unique ID query detected, using search query: '{search_query}'")
        
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
            
            # Try explicit namespace parameter
            namespace_param = None
            if hasattr(vectorstore, 'namespace'):
                namespace_param = vectorstore.namespace
            elif hasattr(vectorstore, '_namespace'):
                namespace_param = vectorstore._namespace
            
            if namespace_param:
                print(f"Using explicit namespace parameter: {namespace_param}")
                try:
                    docs = vectorstore.similarity_search(search_query, k=5, namespace=namespace_param)
                    print(f"Found {len(docs)} documents in similarity search with explicit namespace")
                except Exception as e:
                    print(f"Error with explicit namespace parameter: {str(e)}")
                    docs = vectorstore.similarity_search(search_query, k=5)
                    print(f"Found {len(docs)} documents in similarity search without namespace parameter")
            else:
                docs = vectorstore.similarity_search(search_query, k=5)
                print(f"Found {len(docs)} documents in similarity search")
            
            if len(docs) > 0:
                # Print document IDs for debugging
                doc_ids = [doc.metadata.get('id', 'unknown') for doc in docs]
                print(f"Document IDs: {doc_ids}")
                
                # Print full document information
                for i, doc in enumerate(docs):
                    print(f"Document {i+1}:")
                    if hasattr(doc, 'page_content'):
                        print(f"  Content (first 100 chars): {doc.page_content[:100]}...")
                    if hasattr(doc, 'metadata'):
                        print(f"  Metadata: {doc.metadata}")
                    else:
                        print(f"  Document has no metadata")
                
                # Join document contents
                retrieved_context = "\n\n".join([doc.page_content for doc in docs if hasattr(doc, 'page_content')])
                print(f"Retrieved context: {retrieved_context[:200]}...")
            else:
                print("WARNING: No documents returned from vector search")
                # Try a more general search if specific query returned nothing
                if is_identity_query or is_experience_query or is_unique_id_query:
                    # Try an even more general search for personal information
                    generic_search_query = "personal profile resume CV credentials contact information test-doc unique identifier"
                else:
                    generic_search_query = "general information"
                    
                print(f"Trying generic search with: '{generic_search_query}'")
                try:
                    docs = vectorstore.similarity_search(generic_search_query, k=5)
                    if len(docs) > 0:
                        print(f"Found {len(docs)} documents in generic search")
                        retrieved_context = "\n\n".join([doc.page_content for doc in docs if hasattr(doc, 'page_content')])
                        print(f"Retrieved context from generic search: {retrieved_context[:200]}...")
                    else:
                        print("WARNING: Even generic search returned no documents")
                except Exception as e:
                    print(f"Error in generic search: {str(e)}")
        except Exception as e:
            print(f"Error in primary vector search: {str(e)}")
            retrieved_context = ""
        
        # If query might be about user, do a second search with user's name
        if user_search_needed:
            try:
                user_docs = vectorstore.similarity_search(f"information about {user_info['name']}", k=2)
                if user_docs and len(user_docs) > 0:
                    user_context = "\n\n".join([doc.page_content for doc in user_docs if hasattr(doc, 'page_content')])
                    
                    # Extract structured personal information if found
                    if user_context:
                        personal_information = extract_personal_information(user_context)
            except Exception as e:
                print(f"Error in secondary vector search: {str(e)}")
        
        # Special handling for identity/experience queries when they don't return good results
        if (is_identity_query or is_experience_query) and (not retrieved_context or len(retrieved_context) < 100):
            print("Attempting direct document retrieval for identity/experience query")
            try:
                # Try more variations to find identity information
                identity_queries = [
                    "profile bio resume",
                    "about me introduction",
                    "personal information contact details",
                    "professional background experience education"
                ]
                
                # Try each query until we find good results
                for identity_query in identity_queries:
                    try:
                        identity_docs = vectorstore.similarity_search(identity_query, k=3)
                        if identity_docs and len(identity_docs) > 0:
                            identity_context = "\n\n".join([doc.page_content for doc in identity_docs if hasattr(doc, 'page_content')])
                            # Only use this if it's substantial and different from what we already have
                            if len(identity_context) > 100 and identity_context != retrieved_context:
                                print(f"Found better identity context through direct search: '{identity_query}'")
                                retrieved_context = identity_context
                                break
                    except Exception as e:
                        print(f"Error in identity search query '{identity_query}': {str(e)}")
                        continue
            except Exception as e:
                print(f"Error in identity fallback search: {str(e)}")
        
        # If we got no useful identity information, provide a minimal fallback
        if (is_identity_query or is_experience_query) and (not retrieved_context or len(retrieved_context) < 50):
            retrieved_context = "I am a legal professional with expertise in various areas of law including civil, corporate, and constitutional matters. I provide legal consultation and representation services to clients. I have multiple years of experience in the legal field."
        
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