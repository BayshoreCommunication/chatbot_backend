from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
import os
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import openai

def initialize_vectorstore(embeddings):
    """Initialize the Pinecone vector store"""
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
        return pc, index_name, vectorstore
    except Exception as e:
        print(f"Error initializing vectorstore: {str(e)}")
        # Fallback mechanism
        return pc, index_name, None

def add_document_to_vectorstore(vectorstore, pc, index_name, embeddings, file_path=None, url=None, text=None):
    """Add documents to the vectorstore from different sources"""
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
                # Set the global vectorstore instance
                globals()['vectorstore'] = vectorstore
            except Exception as e:
                error_msg = str(e)
                print(f"Error initializing vectorstore: {error_msg}")
                return {"status": "error", "message": f"Index '{index_name}' not found in your Pinecone project. Did you mean one of the following indexes: {', '.join([index.name for index in pc.list_indexes().indexes])}"}
        
        if file_path and (file_path.endswith('.pdf') or file_path.endswith('.txt')):
            print(f"Loading file from {file_path}")
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
            elif file_path.endswith('.txt'):
                print(f"Loading text file: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                        print(f"Loaded text content ({len(text_content)} chars)")
                        documents.append(Document(page_content=text_content))
                except Exception as e:
                    print(f"Error reading text file: {str(e)}")
                    return {"status": "error", "message": f"Error reading text file: {str(e)}"}
            
            print(f"Loaded {len(documents)} documents from file")
        
        if url:
            print(f"Loading content from URL: {url}")
            # Special handling for URLs that start with @ (typically local file references)
            if url.startswith('@'):
                try:
                    # Strip the @ symbol to get the local path
                    local_path = url[1:]
                    print(f"Processing as local file path: {local_path}")
                    
                    # Determine file type and use appropriate loader
                    if local_path.lower().endswith('.pdf'):
                        print(f"Loading as PDF: {local_path}")
                        loader = PyPDFLoader(local_path)
                        documents.extend(loader.load())
                    else:
                        # For plain text files or other formats
                        print(f"Loading as text file: {local_path}")
                        with open(local_path, 'r', encoding='utf-8') as f:
                            text_content = f.read()
                            documents.append(Document(page_content=text_content))
                except Exception as e:
                    print(f"Error loading local file from URL {url}: {str(e)}")
            else:
                # Regular web URL processing
                try:
                    loader = WebBaseLoader(url)
                    documents.extend(loader.load())
                except Exception as e:
                    print(f"Error loading web URL {url}: {str(e)}")
                    # Try alternative method if web loading fails
                    try:
                        import requests
                        response = requests.get(url)
                        if response.status_code == 200:
                            text_content = response.text
                            documents.append(Document(page_content=text_content))
                    except Exception as sub_e:
                        print(f"Alternative URL loading also failed: {str(sub_e)}")
        
        if text:
            print(f"Processing text input of length: {len(text)}")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            split_docs = text_splitter.split_text(text)
            for doc in split_docs:
                documents.append(Document(page_content=doc))
        
        if documents:
            print(f"Processing {len(documents)} documents")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_documents(documents)
            print(f"Created {len(splits)} document chunks")
            
            # Add to the in-memory vector database
            try:
                print(f"Creating new vector store with index: {index_name}")
                
                # Get or create vector store
                if vectorstore is None:
                    try:
                        index = pc.Index(index_name)
                        vectorstore = PineconeVectorStore(index=index, embedding=embeddings, text_key="text")
                        # Set the global vectorstore instance
                        globals()['vectorstore'] = vectorstore
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
                        
                        # Store directly in Pinecone
                        vectorstore.add_texts(
                            texts=[doc_text],
                            ids=[doc_id],
                            metadatas=[doc.metadata] if hasattr(doc, 'metadata') else [{}]
                        )
                        
                        successful_uploads += 1
                    except Exception as e:
                        print(f"Error uploading document {i}: {str(e)}")
                
                # Verify documents were added by performing a test query
                if successful_uploads > 0:
                    try:
                        test_query = "test query"
                        test_docs = vectorstore.similarity_search(test_query, k=1)
                        print(f"Test query found {len(test_docs)} documents - vectorstore is working")
                    except Exception as e:
                        print(f"Warning: Test query after document upload failed: {str(e)}")
                
                print(f"Successfully added {successful_uploads} documents to the vector store")
                # Ensure global vectorstore is updated
                if 'vectorstore' in globals():
                    globals()['vectorstore'] = vectorstore
                
                return {"status": "success", "message": f"Added {successful_uploads} document chunks to vectorstore"}
            except Exception as e:
                print(f"Error in vector store creation: {str(e)}")
                return {"status": "error", "message": str(e)}
    
    except openai.RateLimitError as e:
        return {"status": "error", "message": str(e), "error_type": "openai_quota_exceeded"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    return {"status": "error", "message": "No documents provided"} 