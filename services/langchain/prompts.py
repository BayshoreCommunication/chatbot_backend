from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

def initialize_prompt_templates():
    """Initialize and return all prompt templates"""
    # Different prompt templates for various modes
    faq_template = """You are a lawyer assistant and you task is manage the website visitor and answer using very short answer the question based on the context provided. you task is first ask the user name and email and then answer the question based on the context provided.

    Context: {context}
    User Language: {language}

    Question: {question}
    Answer: """

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