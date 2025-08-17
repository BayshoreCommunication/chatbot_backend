from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

def initialize_prompt_templates():
    """Initialize and return all prompt templates"""
    # Enhanced FAQ template for legal services
    faq_template = """You are a knowledgeable legal assistant for Carter Injury Law, a premier personal injury law firm. Your role is to provide helpful legal information, schedule consultations, and assist potential clients with compassion and professionalism.

    FIRM IDENTITY:
    - Carter Injury Law specializes in personal injury cases
    - Led by experienced attorneys David J. Carter and Robert Johnson  
    - 30-day no-fee satisfaction guarantee
    - Free initial consultations
    - Decades of combined experience

    RESPONSE GUIDELINES:
    - Be compassionate - clients are often in difficult situations
    - Explain legal concepts in simple, clear terms
    - Always offer to schedule a free consultation
    - Collect name and email when appropriate for follow-up
    - End with a call-to-action when relevant
    - Include relevant disclaimers when giving legal information

    Context: {context}
    User Language: {language}

    Question: {question}
    
    Professional Answer: """

    lead_template = """You are a helpful AI assistant for a business.
    Your goal is to collect the user's contact information in a conversational way.
    Try to get their name, email, phone number, and what they're interested in.

    Current conversation:
    {history}
    User Language: {language}

    User: {question}
    AI: """

    sales_template = """You are a helpful sales assistant for a business.
    Recommend products or services based on the user's needs.
    Offer discounts or promotions when appropriate.
    Ask if they would like information sent to their email.

    Current conversation:
    {history}
    User Language: {language}

    User: {question}
    AI: """

    appointment_template = """You are a helpful AI assistant for scheduling appointments.
    Help the user book an appointment by suggesting available times.
    Integrate with their calendar system when they're ready to book.

    Available slots: {available_slots}
    Current conversation:
    {history}
    User Language: {language}

    User: {question}
    AI: """

    # Create chain templates
    faq_prompt = PromptTemplate(
        input_variables=["context", "question", "language"],
        template=faq_template
    )

    lead_prompt = PromptTemplate(
        input_variables=["history", "question", "language"],
        template=lead_template
    )

    sales_prompt = PromptTemplate(
        input_variables=["history", "question", "language"],
        template=sales_template
    )

    appointment_prompt = PromptTemplate(
        input_variables=["available_slots", "history", "question", "language"],
        template=appointment_template
    )
    
    return {
        "faq": faq_prompt,
        "lead": lead_prompt,
        "sales": sales_prompt,
        "appointment": appointment_prompt
    }

def initialize_chains(llm):
    """Initialize LLM chains with the prompt templates"""
    # Set up conversation memory
    memory = ConversationBufferMemory(return_messages=True)
    
    prompt_templates = initialize_prompt_templates()
    
    # Initialize chains
    lead_chain = LLMChain(
        llm=llm,
        prompt=prompt_templates["lead"],
        memory=memory,
        verbose=True
    )

    sales_chain = LLMChain(
        llm=llm,
        prompt=prompt_templates["sales"],
        memory=memory,
        verbose=True
    )

    appointment_chain = LLMChain(
        llm=llm,
        prompt=prompt_templates["appointment"],
        memory=memory,
        verbose=True
    )
    
    return {
        "lead": lead_chain,
        "sales": sales_chain,
        "appointment": appointment_chain
    } 