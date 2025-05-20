import re
import openai
import json
from services.langchain.knowledge import search_knowledge_base

def handle_name_collection(query, user_data, mode, language):
    """Handle collection of user's name"""
    # Check for skip request first
    skip_keywords = ["skip", "don't need", "not now", "later", "no thanks", "ignore", "anonymous", 
                     "no", "nope", "don't want", "dont want", "i don't", "i dont", "not interested", 
                     "won't share", "wont share", "no name", "don't share", "dont share"]
    refusal_patterns = [
        "i don't want to share",
        "i dont want to share",
        "don't want to give",
        "dont want to give",
        "prefer not to",
        "rather not",
        "no thank you",
    ]
    
    # Check if the query matches any skip keywords or refusal patterns
    is_skip_request = any(keyword in query.lower() for keyword in skip_keywords)
    is_refusal = any(pattern in query.lower() for pattern in refusal_patterns)
    
    if is_skip_request or is_refusal or query.lower() == "no":
        user_data["name"] = "Guest User"
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": "That's fine. Could you please share your email address so I can better assist you? (or type 'skip' if you prefer not to share)"
        })
        
        return {
            "answer": "That's fine. Could you please share your email address so I can better assist you? (or type 'skip' if you prefer not to share)",
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
        
    # If query is empty (first message), just ask for name
    if not query.strip():
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": "Hello! Before we begin, may I know your name? (or type 'skip' if you prefer not to share)"
        })
        
        return {
            "answer": "Hello! Before we begin, may I know your name? (or type 'skip' if you prefer not to share)",
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
    
    # Use OpenAI to extract name
    name_extraction_prompt = f"""
    Extract the person's name from the following text. The text might be an introduction or greeting.
    
    Text: "{query}"
    
    Rules:
    1. Only extract actual names of people, not greetings or other words
    2. If no clear name is found, or if the text appears to be a refusal to provide a name, respond with "No name found"
    3. Return the full name if available (first and last name)
    4. Don't include titles (Mr, Mrs, Dr, etc.)
    5. Check if the text contains refusal phrases like "don't want to share", "won't give my name", etc.
    
    Output only the extracted name, nothing else.
    """
    
    try:
        # Call OpenAI for name extraction
        name_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": name_extraction_prompt}],
            max_tokens=20,
            temperature=0.1
        )
        
        extracted_name = name_response.choices[0].message.content.strip()
        
        # Check if a valid name was found
        if extracted_name and "no name found" not in extracted_name.lower():
            print(f"AI extracted name: {extracted_name}")
            name = extracted_name
        else:
            # Fall back to basic extraction if query looks like just a name
            # Only treat as name if we're confident it's not a refusal
            if (not query.endswith("?") and len(query.split()) <= 3 and 
                not any(keyword in query.lower() for keyword in skip_keywords) and
                not any(pattern in query.lower() for pattern in refusal_patterns)):
                name = query.strip()
            else:
                name = None
    except Exception as e:
        print(f"Error in AI name extraction: {str(e)}")
        # Fall back to regex patterns if AI extraction fails
        name = extract_name_with_regex(query)
    
    # If we found a name, use it
    if name:
        user_data["name"] = name
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": f"Nice to meet you, {name}! Could you please share your email address so I can better assist you? (or type 'skip' if you prefer not to share)"
        })
        
        return {
            "answer": f"Nice to meet you, {name}! Could you please share your email address so I can better assist you? (or type 'skip' if you prefer not to share)",
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
    else:
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": "I didn't catch your name. Could you please tell me your name? (or type 'skip' if you prefer not to share)"
        })
        
        return {
            "answer": "I didn't catch your name. Could you please tell me your name? (or type 'skip' if you prefer not to share)",
            "mode": mode,
            "language": language,
            "user_data": user_data
        }

def extract_name_with_regex(query):
    """Extract name using regex patterns as a fallback method"""
    from re import findall, IGNORECASE
    
    name_extraction_patterns = [
        r"(?:my name is|i am|i'm|this is) ([A-Za-z\s\.]+(?:\s[A-Za-z\.]+){0,4})",
        r"(?:hi|hello|hey)(?:,|!) (?:i am|i'm|this is) ([A-Za-z\s\.]+(?:\s[A-Za-z\.]+){0,4})",
        r"(?:^|\s)([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,3})",
        r"(?:^)([A-Za-z]+(?:\s[A-Za-z]+){0,3})"
    ]
    
    extracted_name = None
    for pattern in name_extraction_patterns:
        matches = findall(pattern, query, IGNORECASE)
        if matches:
            for match in matches:
                candidate = match.strip()
                common_words = ["hi", "hello", "hey", "thanks", "thank you", "please", "looking", "want", "need"]
                if (len(candidate) > 2 and 
                    " " in candidate and 
                    not any(word == candidate.lower() for word in common_words) and
                    len(candidate.split()) <= 4):
                    extracted_name = candidate
                    break
            if extracted_name:
                break
    
    return extracted_name

def handle_email_collection(query, user_data, mode, language):
    """Handle collection of user's email"""
    # Check for skip request
    skip_keywords = ["skip", "don't need", "not now", "later", "no thanks", "ignore", "anonymous", 
                     "no", "nope", "don't want", "dont want", "i don't", "i dont", "not interested",
                     "won't share", "wont share", "no email", "don't share", "dont share"]
    refusal_patterns = [
        "i don't want to share",
        "i dont want to share",
        "don't want to give",
        "dont want to give",
        "prefer not to",
        "rather not",
        "no thank you",
        "won't give",
        "wont give",
    ]
    
    # Check if the query matches any skip keywords or refusal patterns
    is_skip_request = any(keyword in query.lower() for keyword in skip_keywords)
    is_refusal = any(pattern in query.lower() for pattern in refusal_patterns)
    
    if is_skip_request or is_refusal or query.lower() == "no":
        user_data["email"] = "anonymous@user.com"
        
        # Get identity information to introduce properly
        try:
            from services.langchain.engine import get_vectorstore
            vectorstore = get_vectorstore()
            if vectorstore:
                # Try to get basic information about the uploaded identity
                retrieved_context, _ = search_knowledge_base("personal profile introduction", vectorstore, user_data)
                if retrieved_context:
                    # Create a welcome based on the identity information
                    welcome_prompt = f"""
                    Create a very brief welcome message (maximum 2 sentences) for a user. 
                    Use the following information about yourself to create this message.
                    Speak in first person as if YOU are this person. Use "I" statements.
                    
                    YOUR INFORMATION:
                    {retrieved_context}
                    
                    Examples:
                    "Welcome! I'm Dr. Smith, a cardiologist with 15 years of experience. How can I assist you today?"
                    "I'm Sarah Johnson, your legal consultant specializing in family law. What can I help you with?"
                    """
                    
                    welcome_response = openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": welcome_prompt}],
                        max_tokens=100,
                        temperature=0.7
                    )
                    
                    intro_message = welcome_response.choices[0].message.content.strip()
                else:
                    intro_message = "Thank you. How can I assist you today?"
            else:
                intro_message = "Thank you. How can I assist you today?"
                
        except Exception as e:
            print(f"Error generating identity welcome: {str(e)}")
            intro_message = "Thank you. How can I assist you today?"
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": intro_message
        })
        
        return {
            "answer": intro_message,
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
    
    # Check if the query contains an email address
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", query)
    
    if email_match:
        email = email_match.group(0)
        user_data["email"] = email
        
        # Get identity information to introduce properly
        try:
            from services.langchain.engine import get_vectorstore
            vectorstore = get_vectorstore()
            if vectorstore:
                # Try to get basic information about the uploaded identity
                retrieved_context, _ = search_knowledge_base("personal profile introduction", vectorstore, user_data)
                if retrieved_context:
                    # Create a welcome based on the identity information
                    welcome_prompt = f"""
                    Create a brief welcome message for a user who has just provided their email. 
                    Use the following information about yourself to create this message.
                    Speak in first person as if YOU are this person. Use "I" statements.
                    Make sure to thank them for their email and introduce yourself briefly.
                    
                    YOUR INFORMATION:
                    {retrieved_context}
                    
                    USER NAME: {user_data.get("name", "there")}
                    USER EMAIL: {email}
                    
                    Examples:
                    "Thank you for your email! I'm Dr. Smith, a cardiologist with 15 years of experience. How can I assist you today?"
                    "Thanks for sharing your email. I'm Sarah Johnson, your legal consultant specializing in family law. What can I help you with?"
                    """
                    
                    welcome_response = openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": welcome_prompt}],
                        max_tokens=100,
                        temperature=0.7
                    )
                    
                    intro_message = welcome_response.choices[0].message.content.strip()
                else:
                    intro_message = f"Thank you for providing your email. How can I assist you today?"
            else:
                intro_message = f"Thank you for providing your email. How can I assist you today?"
                
        except Exception as e:
            print(f"Error generating identity welcome: {str(e)}")
            intro_message = f"Thank you for providing your email. How can I assist you today?"
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": intro_message
        })
        
        return {
            "answer": intro_message,
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
    else:
        # Check for explicit refusal again to avoid repeated email prompts
        if any(refusal in query.lower() for refusal in ["don't want", "dont want", "no thanks", "not giving", "won't give"]):
            # Set anonymous email and proceed
            user_data["email"] = "anonymous@user.com"
            
            intro_message = "That's fine. How can I assist you today?"
            
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": intro_message
            })
            
            return {
                "answer": intro_message,
                "mode": mode,
                "language": language,
                "user_data": user_data
            }
        else:
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": "Please provide a valid email address so I can better assist you. (or type 'skip' if you prefer not to share)"
            })
            
            return {
                "answer": "Please provide a valid email address so I can better assist you. (or type 'skip' if you prefer not to share)",
                "mode": mode,
                "language": language,
                "user_data": user_data
            }

def extract_personal_information(user_context):
    """Extract structured personal information from user data context"""
    if not user_context:
        return {}
        
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
        
        return json.loads(personal_info_response.choices[0].message.content)
    except Exception as e:
        print(f"Error extracting personal information: {str(e)}")
        return {} 