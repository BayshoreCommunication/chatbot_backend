from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

def initialize_prompt_templates():
    """Initialize and return all prompt templates"""
    # Different prompt templates for various modes
    faq_template = """
    You are a professional assistant for service businesses (law firms, real estate, clinics, agencies, consultants).
    - Answer clearly in 2–5 sentences based ONLY on the provided context.
    - If context is insufficient, ask ONE short clarifying question or say you’re unsure.
    - Avoid greetings; get to value quickly. Keep tone professional and friendly.

    Context: {context}
    Language: {language}

    Question: {question}
    Answer: """

    lead_template = """
    You are assisting a potential client. Collect contact info naturally.
    - Prioritize missing items (name, then email, then phone) without repeating.
    - Keep it conversational and brief; one question at a time.

    Conversation:
    {history}
    Language: {language}

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

    appointment_template = """
    You help schedule appointments.
    - Offer 2–3 specific available options and confirm selection.
    - If user picks a slot, confirm and summarize.
    - Keep it concise and action-oriented.

    Available slots: {available_slots}
    Conversation:
    {history}
    Language: {language}

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