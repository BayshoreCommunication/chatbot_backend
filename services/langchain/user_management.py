import re
import openai
import json

def handle_name_collection(query, user_data, mode, language):
    """Handle collection of user's name"""
    # Use OpenAI to extract name
    name_extraction_prompt = f"""
    Extract the person's name from the following text. The text might be an introduction or greeting.
    
    Text: "{query}"
    
    Rules:
    1. Only extract actual names of people, not greetings or other words
    2. If no clear name is found, respond with "No name found"
    3. Return the full name if available (first and last name)
    4. Don't include titles (Mr, Mrs, Dr, etc.)
    
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
            if not query.endswith("?") and len(query.split()) <= 5:
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
            "content": f"Nice to meet you, {name}! Could you please share your email address so I can better assist you?"
        })
        
        return {
            "answer": f"Nice to meet you, {name}! Could you please share your email address so I can better assist you?",
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
    else:
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": "Before we proceed, may I know your name? (or type 'skip' if you prefer not to share)"
        })
        
        return {
            "answer": "Before we proceed, may I know your name? (or type 'skip' if you prefer not to share)",
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
    # Check if the query contains an email address
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", query)
    
    if email_match:
        email = email_match.group(0)
        user_data["email"] = email
        
        # Add this interaction to history
        user_data["conversation_history"].append({
            "role": "assistant", 
            "content": f"Thank you for providing your email. How can I assist you today?"
        })
        
        return {
            "answer": f"Thank you for providing your email. How can I assist you today?",
            "mode": mode,
            "language": language,
            "user_data": user_data
        }
    else:
        # Check for skip request
        skip_keywords = ["skip", "don't need", "not now", "later", "no thanks", "ignore"]
        is_skip_request = any(keyword in query.lower() for keyword in skip_keywords)
        
        if is_skip_request:
            user_data["email"] = "anonymous@user.com"
            
            # Add this interaction to history
            user_data["conversation_history"].append({
                "role": "assistant", 
                "content": "No problem. How can I assist you today?"
            })
            
            return {
                "answer": "No problem. How can I assist you today?",
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