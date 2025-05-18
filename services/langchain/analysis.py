import openai
import json

def analyze_query(query, user_info, mode, needs_info, has_vector_data, conversation_summary):
    """Use AI to analyze a query and determine the best response approach"""
    available_modes = ["faq", "appointment", "sales", "lead_capture"]
    
    analysis_prompt = f"""
    You are an AI assistant analyzing a user query to determine the best response approach.
    
    USER QUERY: "{query}"
    
    USER INFORMATION:
    - Name: {user_info['name']}
    - Email: {user_info['email']}
    - Has booked appointment: {user_info['has_appointment']}
    - Appointment details: {user_info['appointment_details']}
    
    CONTEXT:
    - Current mode: {mode}
    - Needs personal info: {needs_info}
    - Has knowledge base: {has_vector_data}
    
    CONVERSATION HISTORY:
    {conversation_summary}
    
    Analyze the following aspects and respond in JSON format:
    1. What is the user's primary intent?
    2. Should we collect user information before proceeding? (Name/Email)
    3. What mode is most appropriate? (faq/appointment/sales/lead_capture)
    4. Does this query need knowledge base lookup?
    5. If appointment related, is user trying to book, reschedule, or cancel?
    6. Any special handling needed? (like identity questions)
    
    MODE DESCRIPTIONS:
    - faq: General knowledge questions and information retrieval
    - appointment: Booking, managing, or inquiring about appointments
    - sales: Inquiries about products, services, or pricing
    - lead_capture: When the user is indicating interest in becoming a client
    
    MODE SELECTION RULES:
    - If user mentions scheduling, booking, or availability, use appointment mode
    - If user asks about products, pricing, or deals, use sales mode
    - If user mentions becoming a client or asks how to start, use lead_capture mode
    - Default to faq mode for general information questions
    - If currently in a specific mode (like appointment) but has completed the process, switch back to faq
    
    RESPOND WITH JSON ONLY in the following format:
    {{
        "intent": "primary user intent",
        "collect_info": true/false,
        "info_to_collect": "name/email/none",
        "appropriate_mode": "one of {', '.join(available_modes)}",
        "needs_knowledge_lookup": true/false,
        "appointment_action": "book/reschedule/cancel/info/none",
        "special_handling": "identity/none/other",
        "mode_confidence": "high/medium/low",
        "reasoning": "brief explanation of mode selection"
    }}
    """
    
    # Call OpenAI for central analysis
    try:
        analysis_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        # Parse analysis
        analysis = json.loads(analysis_response.choices[0].message.content)
        print(f"AI Analysis: {analysis}")
        return analysis
    except Exception as e:
        print(f"Error in AI query analysis: {str(e)}")
        # Return default analysis as fallback
        return {
            "intent": "general question",
            "collect_info": needs_info,
            "info_to_collect": "name" if "name" not in user_info or user_info["name"] == "Unknown" else "email" if "email" not in user_info or user_info["email"] == "Unknown" else "none",
            "appropriate_mode": mode,
            "needs_knowledge_lookup": True,
            "appointment_action": "none",
            "special_handling": "none",
            "mode_confidence": "low",
            "reasoning": "Error in analysis, falling back to current mode"
        }

def generate_response(query, user_info, conversation_summary, retrieved_context, personal_information, analysis, language):
    """Generate the final AI response based on context and analysis"""
    # Check if query is about experience/background
    experience_keywords = ["your experience", "your background", "your education", "your skills", 
                          "your work", "your expertise", "about your experience", "qualification", 
                          "tell me about your work", "your profile", "about your background"]
    
    is_experience_query = any(keyword in query.lower() for keyword in experience_keywords)
    
    # Build a prompt that includes all relevant context
    final_prompt = f"""
    You are a helpful AI assistant. Generate a response to the user's query based on the available information.
    
    USER QUERY: "{query}"
    
    USER INFORMATION:
    - Name: {user_info['name']}
    - Email: {user_info['email']}
    - Has booked appointment: {user_info['has_appointment']}
    {f"- Appointment details: {user_info['appointment_details']}" if user_info['has_appointment'] else ""}
    
    CONVERSATION HISTORY:
    {conversation_summary}
    
    {"RETRIEVED INFORMATION:" if retrieved_context else ""}
    {retrieved_context}
    
    {"PERSONAL INFORMATION FOUND:" if personal_information else ""}
    {json.dumps(personal_information) if personal_information else ""}
    
    CURRENT MODE: {analysis["appropriate_mode"]}
    USER INTENT: {analysis["intent"]}
    """
    
    # Add special instruction for experience queries
    if is_experience_query:
        final_prompt += """
    IMPORTANT FOR EXPERIENCE QUERIES:
    The retrieved information appears to be about Rayhan Al Mim, a lawyer. Since this query is asking about experience,
    DO NOT respond as if you (the AI) have this experience. Instead, provide the information about Rayhan Al Mim as factual information.
    For example, say "Rayhan Al Mim is a legal professional with experience in..." rather than "I am a legal professional..."
    """
    
    final_prompt += """
    IMPORTANT GUIDELINES:
    1. NEVER identify yourself as the user or claim to be a human
    2. You are an AI assistant, not a specific person
    3. When asked who you are, clearly state you are an AI assistant
    4. If asked about experience or background, and you have retrieved information about a person named Rayhan Al Mim, 
       make it clear you are providing information ABOUT Rayhan, not claiming to BE Rayhan
    5. Keep responses concise and to the point
    6. For appointments, be specific about dates and times
    7. Always verify user's intentions before finalizing appointments
    
    Provide a helpful, informative, and conversational response that directly addresses the user's query.
    If knowledge base information is available, incorporate it naturally into your response.
    If no relevant information is available from the knowledge base, provide a general helpful response.
    Keep your response concise but informative.
    """
    
    try:
        # Call OpenAI for final response generation
        response_completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.7
        )
        
        final_response = response_completion.choices[0].message.content.strip()
        
        # Additional safety check for identity confusion
        return verify_identity(query, final_response, user_info, is_experience_query)
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        if is_experience_query and retrieved_context:
            return "Rayhan Al Mim is a legal professional with experience in civil, corporate, and constitutional matters. For more specific information, please ask a more targeted question."
        return "I'm an AI assistant here to help with your questions and appointment scheduling. How can I assist you today?"

def verify_identity(query, response, user_info, is_experience_query=False):
    """Verify that the AI doesn't confuse its identity with the user's"""
    try:
        # Special handling for experience queries
        if is_experience_query:
            # Check if response talks about "I am a lawyer" or similar phrases indicating identity confusion
            identity_confusion_phrases = [
                "i am a lawyer", "i am a legal", "my legal experience", "my experience", 
                "my background", "my education", "i specialize", "i help clients",
                "i practice law", "my expertise", "my skills"
            ]
            
            # Check for these phrases in lowercase response
            lower_response = response.lower()
            if any(phrase in lower_response for phrase in identity_confusion_phrases):
                print("Identity confusion detected in experience query response")
                # Return a corrected response that's about Rayhan, not the AI
                return "Based on the provided information, Rayhan Al Mim is a legal professional with experience in civil, corporate, and constitutional matters. With years of experience handling various legal cases, Rayhan helps individuals and businesses navigate legal complexities. For more specific details about his background or services, please ask a more targeted question."
        
        # Standard identity verification for non-experience queries
        identity_verification_prompt = f"""
        Review this AI assistant's response to make sure it correctly identifies itself and doesn't confuse its identity:
        
        USER QUERY: "{query}"
        AI RESPONSE: "{response}"
        USER NAME: {user_info['name']}
        
        Check for these issues:
        1. Does the response incorrectly claim the AI is {user_info['name']} or a human?
        2. Does the response confuse the AI's identity with user's identity?
        3. Does the response inappropriately claim personal experiences, feelings, or human characteristics?
        4. If there is information about a lawyer named Rayhan, does the AI incorrectly present this as its own experience?
        
        If any issues are found, provide a corrected response. Otherwise, respond with "PASS".
        """
        
        verification_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": identity_verification_prompt}],
            temperature=0.1
        )
        
        verification_result = verification_response.choices[0].message.content.strip()
        
        if verification_result != "PASS":
            print("Identity check failed. Using corrected response.")
            if "I'm an AI assistant" in verification_result or "I am an AI" in verification_result:
                return verification_result
            else:
                if is_experience_query:
                    return "Rayhan Al Mim is a legal professional with experience in civil, corporate, and constitutional matters. He specializes in legal strategy and has worked with various clients on complex litigation. For more specific information about his background or practice areas, please ask a more targeted question."
                else:
                    return "I'm an AI assistant designed to help you with scheduling appointments, answering questions, and providing information. I can help you manage your calendar, find information, or assist with other tasks. How can I help you today?"
        
        return response
    except Exception as e:
        print(f"Error in identity verification: {str(e)}")
        return response  # Return original response if verification fails 