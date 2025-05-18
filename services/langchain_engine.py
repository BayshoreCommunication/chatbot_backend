from langchain_openai import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain.chains import ConversationChain, LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
from services.language_detect import detect_language
from services.notification import send_email_notification
import json
import openai
import numpy as np
from langchain.embeddings.base import Embeddings

load_dotenv()

print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY")) 

# Define a custom embedding class that reduces vector dimensions
class DimensionReducedEmbeddings(Embeddings):
    def __init__(self, base_embeddings, target_dim=1024):
        self.base_embeddings = base_embeddings
        self.target_dim = target_dim
        
    def embed_documents(self, texts):
        # Get the original embeddings
        original_embeddings = self.base_embeddings.embed_documents(texts)
        # Reduce dimensions and convert to Python float
        reduced_embeddings = []
        for emb in original_embeddings:
            # Convert to Python list of floats
            reduced_emb = [float(x) for x in emb[:self.target_dim]]
            # Normalize
            reduced_embeddings.append(self._normalize(reduced_emb))
        return reduced_embeddings
    
    def embed_query(self, text):
        # Get the original embedding
        original_embedding = self.base_embeddings.embed_query(text)
        # Reduce dimensions and convert to Python floats
        reduced_embedding = [float(x) for x in original_embedding[:self.target_dim]]
        # Normalize the embedding after reduction
        return self._normalize(reduced_embedding)
    
    def _normalize(self, v):
        # Normalize the vector to have unit length
        norm = np.linalg.norm(v)
        if norm > 0:
            return [float(x / norm) for x in v]
        return [float(x) for x in v]

# Initialize OpenAI
llm = ChatOpenAI(
    model_name="gpt-3.5-turbo", 
    temperature=0.5,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base="https://api.openai.com/v1"
)

# Use actual OpenAI embeddings
base_embeddings = OpenAIEmbeddings(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base="https://api.openai.com/v1"
)

# Create dimension-reduced embeddings to match Pinecone index
embeddings = DimensionReducedEmbeddings(base_embeddings, target_dim=1024)

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX")
print(f"PINECONE_INDEX: {index_name}")  # Debug print

# Use fallback value if index_name is None
if index_name is None:
    index_name = "bayshoreai"
    print(f"Using fallback index_name: {index_name}")

# Check if index exists, if not create it
indexes = pc.list_indexes()
existing_index_names = [index.name for index in indexes.indexes]

print(f"Existing indexes: {existing_index_names}")

if index_name not in existing_index_names:
    pc.create_index(
        name=index_name,
        dimension=1536,  # OpenAI embeddings dimension
        metric="cosine"
    )

try:
    index = pc.Index(index_name)
    vectorstore = PineconeVectorStore(index=index, embedding=embeddings, text_key="text")
    print(f"Successfully initialized vectorstore with index: {index_name}")
except Exception as e:
    print(f"Error initializing vectorstore: {str(e)}")
    # Fallback mechanism
    vectorstore = None

# Set up QA chain
qa_chain = load_qa_chain(llm, chain_type="stuff")

# Set up conversation memory
memory = ConversationBufferMemory(return_messages=True)

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

# Initialize chains
lead_chain = LLMChain(
    llm=llm,
    prompt=lead_prompt,
    memory=memory,
    verbose=True
)

sales_chain = LLMChain(
    llm=llm,
    prompt=sales_prompt,
    memory=memory,
    verbose=True
)

appointment_chain = LLMChain(
    llm=llm,
    prompt=appointment_prompt,
    memory=memory,
    verbose=True
)

def add_document_to_vectorstore(file_path=None, url=None, text=None):
    """Add documents to the vectorstore from different sources"""
    global vectorstore, index_name, pc, embeddings
    documents = []
    
    # HARD FALLBACK: Ensure index_name is NEVER None at this point
    if index_name is None:
        index_name = "bayshoreai"
        print(f"CRITICAL: Using hardcoded fallback index_name: {index_name}")
    
    try:
        # If vectorstore is None, try to reinitialize
        if vectorstore is None:
            try:
                print(f"Attempting to initialize vectorstore with index: {index_name}")
                index = pc.Index(index_name)
                vectorstore = PineconeVectorStore(index=index, embedding=embeddings, text_key="text")
                print(f"Reinitialized vectorstore with index: {index_name}")
            except Exception as e:
                error_msg = str(e)
                print(f"Error initializing vectorstore: {error_msg}")
                return {"status": "error", "message": f"Index '{index_name}' not found in your Pinecone project. Did you mean one of the following indexes: {', '.join([index.name for index in pc.list_indexes().indexes])}"}
        
        if file_path and file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
        
        if url:
            loader = WebBaseLoader(url)
            documents.extend(loader.load())
        
        if text:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            split_docs = text_splitter.split_text(text)
            for doc in split_docs:
                from langchain_core.documents import Document
                documents.append(Document(page_content=doc))
        
        if documents:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_documents(documents)
            
            # Add to the in-memory vector database
            try:
                print(f"Creating new vector store with index: {index_name}")
                
                # DIRECT APPROACH: Don't use PineconeVectorStore.from_documents
                # Instead manually embed and insert each document
                
                # Get the Pinecone index directly
                if index_name is None:
                    index_name = "bayshoreai"  # Final fallback
                
                # Get or create vector store
                if vectorstore is None:
                    try:
                        index = pc.Index(index_name)
                        vectorstore = PineconeVectorStore(index=index, embedding=embeddings, text_key="text")
                    except Exception as e:
                        print(f"Error getting index: {str(e)}")
                        return {"status": "error", "message": str(e)}
                
                # Process each document manually
                successful_uploads = 0
                for i, doc in enumerate(splits):
                    try:
                        # Get the document text
                        doc_text = doc.page_content
                        
                        # Create an ID for this document
                        doc_id = f"doc_{i}_{abs(hash(doc_text)) % 10000}"
                        
                        # Get embedding vector directly
                        embedding_vector = embeddings.embed_query(doc_text)
                        
                        # Store directly in Pinecone
                        vectorstore.add_texts(
                            texts=[doc_text],
                            ids=[doc_id],
                            metadatas=[doc.metadata] if hasattr(doc, 'metadata') else [{}]
                        )
                        
                        successful_uploads += 1
                    except Exception as e:
                        print(f"Error uploading document {i}: {str(e)}")
                
                return {"status": "success", "message": f"Added {successful_uploads} document chunks to vectorstore"}
            except Exception as e:
                print(f"Error in vector store creation: {str(e)}")
                return {"status": "error", "message": str(e)}
    
    except openai.RateLimitError as e:
        return {"status": "error", "message": str(e), "error_type": "openai_quota_exceeded"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    return {"status": "error", "message": "No documents provided"}

def ask_bot(query: str, mode="faq", user_data=None, available_slots=None):
    """Process user query based on the selected mode"""
    try:
        language = detect_language(query)
        
        if mode == "faq":
            # Retrieve relevant documents from vectorstore
            docs = vectorstore.similarity_search(query, k=4)
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Get response using the FAQ prompt
            response = qa_chain.run(
                input_documents=docs, 
                question=query,
                context=context,
                language=language
            )
            
            return {"answer": response, "mode": mode, "language": language}
        
        elif mode == "lead_capture":
            # Use the lead capture chain to get contact info
            response = lead_chain.predict(
                question=query,
                language=language
            )
            
            # Check if we have collected all necessary information
            if user_data and all(key in user_data for key in ["name", "email", "phone", "inquiry"]):
                # Send notification to business owner
                send_email_notification("New Lead Captured", json.dumps(user_data))
                
                # You can integrate with CRM systems here (HubSpot, Mailchimp, etc.)
                # Example: hubspot_integration.add_contact(user_data)
                
                return {
                    "answer": response,
                    "mode": mode,
                    "language": language,
                    "lead_complete": True,
                    "user_data": user_data
                }
                
            return {"answer": response, "mode": mode, "language": language}
        
        elif mode == "appointment":
            # Use the appointment chain to handle booking
            response = appointment_chain.predict(
                question=query,
                language=language,
                available_slots=available_slots if available_slots else "No slots provided"
            )
            
            return {"answer": response, "mode": mode, "language": language}
        
        elif mode == "sales":
            # Use the sales chain to handle product recommendations
            response = sales_chain.predict(
                question=query,
                language=language
            )
            
            return {"answer": response, "mode": mode, "language": language}
        
        else:
            # Default to FAQ mode if an invalid mode is provided
            return ask_bot(query, mode="faq")
    
    except openai.RateLimitError as e:
        error_message = str(e)
        return {
            "status": "error", 
            "error_type": "openai_quota_exceeded",
            "message": "OpenAI API quota exceeded. Please check your billing details.",
            "detailed_error": error_message
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "general_error",
            "message": f"An error occurred: {str(e)}"
        }

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