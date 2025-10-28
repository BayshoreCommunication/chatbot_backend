from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
import os
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Backward compatible import for Document
try:
    from langchain_core.documents import Document
except ImportError:
    try:
        from langchain.docstore.document import Document
    except ImportError:
        from langchain.schema import Document
import openai
from services.database import get_organization_by_api_key
import datetime
import uuid
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def initialize_vectorstore(embeddings, api_key=None):
    """Initialize the Pinecone vector store with optional organization namespace"""
    # Initialize Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX")
    print(f"PINECONE_INDEX: {index_name}")  # Debug print
    
    # Get organization namespace if API key is provided
    namespace = None
    if api_key:
        organization = get_organization_by_api_key(api_key)
        if organization:
            namespace = organization.get('pinecone_namespace')
            print(f"Using organization namespace: {namespace}")

    # Use fallback value if index_name is None
    if index_name is None:
        index_name = "bayai"
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
        vectorstore = PineconeVectorStore(
            index=index, 
            embedding=embeddings, 
            text_key="text",
            namespace=namespace
        )
        print(f"Successfully initialized vectorstore with index: {index_name}, namespace: {namespace}")
        return pc, index_name, vectorstore, namespace
    except Exception as e:
        print(f"Error initializing vectorstore: {str(e)}")
        # Fallback mechanism
        return pc, index_name, None, namespace

def add_document_to_vectorstore(vectorstore, pc, index_name, embeddings, api_key=None, file_path=None, url=None, text=None):
    """Add documents to the vectorstore from different sources with organization namespacing"""
    documents = []
    
    # Get organization namespace if API key is provided
    namespace = None
    organization_id = None
    
    if api_key:
        organization = get_organization_by_api_key(api_key)
        if organization:
            namespace = organization.get('pinecone_namespace')
            organization_id = organization.get('id')
            print(f"Using organization namespace: {namespace}")
    
    # Debug outputs - check that all required parameters are provided
    print(f"OpenAI API Key (truncated): {os.getenv('OPENAI_API_KEY')[:10]}...")
    print(f"Pinecone API Key (truncated): {os.getenv('PINECONE_API_KEY')[:10]}...")
    print(f"Index name: {index_name}")
    
    # Ensure index_name is never None
    if index_name is None:
        index_name = "bayai"
        print(f"CRITICAL: Using hardcoded fallback index_name: {index_name}")
    
    # Check if PC connection is established
    if pc is None:
        print("Pinecone connection is None, initializing...")
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    
    # List available indexes
    try:
        indexes = pc.list_indexes()
        existing_index_names = [index.name for index in indexes.indexes]
        print(f"Available indexes: {existing_index_names}")
        
        # Create index if it doesn't exist
        if index_name not in existing_index_names:
            print(f"Creating new index: {index_name}")
            pc.create_index(
                name=index_name,
                dimension=1536,  # OpenAI embeddings dimension
                metric="cosine"
            )
        
        print(f"Successfully connected to index: {index_name}")
    except Exception as e:
        print(f"Error listing/creating indexes: {str(e)}")
        return {"status": "error", "message": f"Error connecting to Pinecone: {str(e)}"}
    
    try:
        # Load documents based on the provided source
        if file_path:
            print(f"Loading file from {file_path}")
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
                documents = loader.load()
                print(f"Loaded {len(documents)} documents from file")
            else:
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
                    documents = [Document(page_content=text)]
                    print(f"Loaded 1 document from file")
                
        elif url:
            print(f"Loading URL from {url}")
            try:
                # Check if the URL contains a parameter for comprehensive scraping
                if "scrape_website=true" in url.lower() or "scrape_site=true" in url.lower():
                    # Extract the actual URL without the parameters
                    base_url = url.split('?')[0] if '?' in url else url
                    
                    # Extract max_pages if specified
                    max_pages = 10  # Default
                    if "max_pages=" in url.lower():
                        try:
                            # Extract the max_pages value
                            for param in url.split('?')[1].split('&'):
                                if param.lower().startswith("max_pages="):
                                    max_pages = int(param.split('=')[1])
                                    break
                        except:
                            pass
                    
                    print(f"Performing comprehensive website scraping of {base_url} with max_pages={max_pages}")
                    documents = scrape_website_content(base_url, max_pages)
                else:
                    # Use standard WebBaseLoader for single page with enhanced error handling
                    print(f"Attempting to load single page: {url}")
                    
                    # Try to access URL first to check if it's reachable
                    import requests
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    
                    try:
                        # Test URL accessibility
                        print(f"Testing URL accessibility: {url}")
                        response = requests.get(url, headers=headers, timeout=15)
                        response.raise_for_status()
                        print(f"URL is accessible. Status code: {response.status_code}")
                        print(f"Content length: {len(response.text)} characters")
                        
                        # Check if content is not empty
                        if len(response.text.strip()) < 100:
                            raise Exception(f"URL returned very little content ({len(response.text)} characters). The page might be empty or require JavaScript.")
                            
                    except requests.exceptions.Timeout:
                        raise Exception(f"Timeout error: The website {url} took too long to respond (>15 seconds). Try again later.")
                    except requests.exceptions.ConnectionError:
                        raise Exception(f"Connection error: Unable to connect to {url}. Check if the website is accessible.")
                    except requests.exceptions.HTTPError as e:
                        if response.status_code == 403:
                            raise Exception(f"Access denied (403): The website {url} is blocking automated requests. This is common with sites using Cloudflare or similar protection.")
                        elif response.status_code == 404:
                            raise Exception(f"Page not found (404): The URL {url} does not exist.")
                        elif response.status_code >= 500:
                            raise Exception(f"Server error ({response.status_code}): The website {url} is experiencing technical difficulties.")
                        else:
                            raise Exception(f"HTTP error {response.status_code}: Unable to access {url}")
                    except Exception as e:
                        raise Exception(f"Network error accessing {url}: {str(e)}")
                    
                    # If URL is accessible, try WebBaseLoader
                    try:
                        print(f"URL test successful, proceeding with WebBaseLoader")
                        loader = WebBaseLoader(url)
                        documents = loader.load()
                        print(f"WebBaseLoader successful")
                    except Exception as e:
                        print(f"WebBaseLoader failed: {str(e)}")
                        # Fallback to manual scraping if WebBaseLoader fails
                        print("Falling back to manual scraping...")
                        documents = scrape_website_content(url, 1)  # Just scrape the single page
                
                print(f"Loaded {len(documents)} documents from URL")
                
                # Validate that we got meaningful content
                total_content_length = sum(len(doc.page_content) for doc in documents)
                if total_content_length < 100:
                    raise Exception(f"Extracted content is too short ({total_content_length} characters). The page might be mostly JavaScript-based or have access restrictions.")
                    
            except Exception as e:
                error_msg = f"Failed to load URL {url}: {str(e)}"
                print(error_msg)
                raise Exception(error_msg)
        
        elif text:
            print(f"Processing text input of length: {len(text)}")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            split_docs = text_splitter.split_text(text)
            print(f"Created {len(split_docs)} document chunks")
            for doc in split_docs:
                documents.append(Document(page_content=doc))
        
        if documents:
            print(f"Processing {len(documents)} documents")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_documents(documents)
            print(f"Created {len(splits)} document chunks")
            
            # Add to the vector database
            try:
                print(f"Storing documents in index: {index_name}")
                
                # Get or create vector store
                if vectorstore is None:
                    print("Vector store is None, creating new instance...")
                    try:
                        # Make sure index_name is passed correctly
                        if not index_name:
                            index_name = "bayai"
                            print(f"Using default index name: {index_name}")
                            
                        # Get Pinecone index
                        index = pc.Index(index_name)
                        print(f"Successfully retrieved index: {index_name}")
                        
                        # Import here to avoid circular imports
                        from langchain_pinecone import PineconeVectorStore
                        
                        # Create the vector store
                        vectorstore = PineconeVectorStore(
                            index=index, 
                            embedding=embeddings, 
                            text_key="text",
                            namespace=namespace
                        )
                        print(f"Created PineconeVectorStore with namespace: {namespace}")
                        
                        # Set the namespace explicitly for easier access later
                        if not hasattr(vectorstore, 'namespace'):
                            setattr(vectorstore, 'namespace', namespace)
                            print(f"Set namespace attribute: {namespace}")
                    except Exception as e:
                        error_msg = str(e)
                        print(f"Error creating vector store: {error_msg}")
                        return {"status": "error", "message": error_msg}
                
                # Process each document manually
                successful_uploads = 0
                document_details = []
                
                for i, doc in enumerate(splits):
                    try:
                        # Get the document text
                        doc_text = doc.page_content
                        
                        # Create an ID for this document
                        doc_id = f"doc_{i}_{abs(hash(doc_text)) % 10000}"
                        
                        # Add organization ID to metadata if available
                        metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                        if api_key:
                            organization = get_organization_by_api_key(api_key)
                            if organization:
                                metadata['organization_id'] = organization.get('id')
                        
                        # Store directly in Pinecone
                        print(f"Adding document {i+1}/{len(splits)} to namespace: {namespace}")
                        vectorstore.add_texts(
                            texts=[doc_text],
                            ids=[doc_id],
                            metadatas=[metadata],
                            namespace=namespace  # Explicitly set namespace here too
                        )
                        
                        # Track successful uploads
                        successful_uploads += 1
                        
                        # Save document details for database tracking
                        document_details.append({
                            "document_id": doc_id,
                            "content_preview": doc_text[:200] + "..." if len(doc_text) > 200 else doc_text,
                            "source_type": "file" if file_path else "url" if url else "text",
                            "source_path": file_path if file_path else url if url else None,
                            "vector_id": doc_id,
                            "namespace": namespace,
                            "metadata": metadata,
                            "created_at": datetime.datetime.utcnow()
                        })
                        
                    except Exception as e:
                        print(f"Error uploading document {i}: {str(e)}")
                
                # Track documents in the database if organization is available
                if organization_id and successful_uploads > 0:
                    try:
                        from services.database import add_organization_document
                        
                        # File-level document record
                        main_doc_id = f"doc_main_{uuid.uuid4().hex[:8]}"
                        source_name = os.path.basename(file_path) if file_path else url if url else "Text input"
                        
                        # Add main document record
                        main_document = {
                            "document_id": main_doc_id,
                            "title": source_name,
                            "source_type": "file" if file_path else "url" if url else "text",
                            "source_path": file_path if file_path else url if url else None,
                            "chunk_count": successful_uploads,
                            "chunks": document_details,
                            "created_at": datetime.datetime.utcnow()
                        }
                        
                        add_organization_document(organization_id, main_document)
                        print(f"Tracked document in database with ID: {main_doc_id}")
                    except Exception as e:
                        print(f"Error tracking document in database: {str(e)}")
                
                # Verify documents were added by performing a test query
                if successful_uploads > 0:
                    try:
                        test_query = "test query"
                        test_docs = vectorstore.similarity_search(test_query, k=1, namespace=namespace)
                        print(f"Test query found {len(test_docs)} documents - vectorstore is working")
                    except Exception as e:
                        print(f"Warning: Test query after document upload failed: {str(e)}")
                
                print(f"Successfully added {successful_uploads} documents to the vector store")
                return {
                    "status": "success", 
                    "message": f"Added {successful_uploads} document chunks to knowledge base",
                    "documents_added": successful_uploads
                }
            except Exception as e:
                print(f"Error adding documents to vector store: {str(e)}")
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": "No documents were created from the provided source"}
    except Exception as e:
        print(f"Error processing documents: {str(e)}")
        return {"status": "error", "message": str(e)}

def scrape_website_content(base_url, max_pages=10):
    """
    Scrape content from a website, following internal links up to max_pages
    
    Args:
        base_url: The starting URL to scrape
        max_pages: Maximum number of pages to scrape
        
    Returns:
        List of Document objects containing the website content
    """
    print(f"Starting comprehensive scraping of {base_url} (max {max_pages} pages)")
    
    # Track visited URLs to avoid duplicates
    visited_urls = set()
    to_visit = [base_url]
    documents = []
    count = 0
    
    # Parse the base domain to stay within the same website
    base_domain = urlparse(base_url).netloc
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    while to_visit and count < max_pages:
        # Get the next URL to visit
        current_url = to_visit.pop(0)
        
        # Skip if already visited
        if current_url in visited_urls:
            continue
            
        print(f"Scraping page {count+1}/{max_pages}: {current_url}")
        
        try:
            # Fetch the page
            response = requests.get(current_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Mark as visited
            visited_urls.add(current_url)
            count += 1
            
            # Parse the page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract text content
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            # Get the main content (prioritize main, article, or div with content)
            main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=lambda c: c and ("content" in c.lower() or "main" in c.lower()))
            
            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                # Fallback to body if no main content identified
                text = soup.get_text(separator="\n", strip=True)
            
            # Clean up text (remove excessive newlines)
            text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
            
            # Create metadata
            metadata = {
                "source": current_url,
                "title": soup.title.string if soup.title else current_url,
            }
            
            # Add to documents
            documents.append(Document(page_content=text, metadata=metadata))
            
            # Find links to other pages on the same domain
            if count < max_pages:
                links = soup.find_all("a", href=True)
                for link in links:
                    href = link["href"]
                    
                    # Resolve relative URLs
                    full_url = urljoin(current_url, href)
                    
                    # Check if the URL is on the same domain and not already visited
                    parsed_url = urlparse(full_url)
                    if (parsed_url.netloc == base_domain or not parsed_url.netloc) and \
                       full_url not in visited_urls and \
                       full_url not in to_visit and \
                       not full_url.endswith(('.pdf', '.jpg', '.png', '.gif')):
                        to_visit.append(full_url)
        
        except Exception as e:
            print(f"Error scraping {current_url}: {str(e)}")
    
    print(f"Completed scraping {count} pages, extracted {len(documents)} documents")
    return documents 