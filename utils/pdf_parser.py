from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from services.mock_embeddings import MockEmbeddings
from langchain_community.vectorstores import FAISS
import os
from dotenv import load_dotenv

load_dotenv()

def load_pdf(file_path):
    """Load and parse a PDF file"""
    loader = PyPDFLoader(file_path)
    return loader.load()

def process_pdf_to_vectorstore(file_path):
    """Process a PDF file and add it to the vector store"""
    # Initialize embeddings
    embeddings = MockEmbeddings()
    
    # Load PDF
    documents = load_pdf(file_path)
    
    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(documents)
    
    # Create a FAISS vectorstore
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    # Save the vectorstore to disk
    vectorstore.save_local("faiss_index")
    
    return {
        "status": "success",
        "document_name": os.path.basename(file_path),
        "chunks": len(splits)
    }