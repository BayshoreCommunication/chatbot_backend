import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()

# Initialize OpenAI embeddings
openai_api_key = os.getenv("OPENAI_API_KEY")
embeddings = OpenAIEmbeddings(
    openai_api_key=openai_api_key,
    openai_api_base="https://api.openai.com/v1"
)

# Initialize Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX")

print(f"OpenAI API Key (truncated): {openai_api_key[:10]}...")
print(f"Pinecone API Key (truncated): {pinecone_api_key[:10]}...")
print(f"Index name: {index_name}")

pc = Pinecone(api_key=pinecone_api_key)

# List all indexes
print("Available indexes:")
indexes = pc.list_indexes()
existing_index_names = [index.name for index in indexes.indexes]
print(existing_index_names)

# Try to connect to the specific index
try:
    index = pc.Index(index_name)
    print(f"Successfully connected to index: {index_name}")
    
    # Create a simple document
    text = """This is a test document to check if document upload to Pinecone works correctly.
    It should be embedded and stored in the vector database.
    If you can find this text later through a similarity search, it means everything works!"""
    
    # Split the document
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_text(text)
    documents = [Document(page_content=doc) for doc in splits]
    
    print(f"Created {len(documents)} document chunks")
    
    # Store documents directly in Pinecone
    print(f"Storing documents in index: {index_name}")
    vectorstore = PineconeVectorStore.from_documents(
        documents=documents, 
        embedding=embeddings, 
        index=index,
        text_key="text"
    )
    
    print("Successfully stored documents in Pinecone!")
    
    # Try to retrieve the stored document
    print("\nTesting retrieval...")
    retrieved_docs = vectorstore.similarity_search("test document", k=1)
    
    if retrieved_docs:
        print(f"Successfully retrieved document: {retrieved_docs[0].page_content[:50]}...")
    else:
        print("No documents retrieved.")
    
except Exception as e:
    print(f"Error: {str(e)}") 