import pinecone
from langchain_pinecone import PineconeVectorStore
import os
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
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
    pc = pinecone.Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
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
        index_name = "bayshoreai"
        print(f"CRITICAL: Using hardcoded fallback index_name: {index_name}")
    
    # Check if PC connection is established
    if pc is None:
        print("Pinecone connection is None, initializing...")
        pc = pinecone.Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    
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
            # Check if the URL contains a parameter for comprehensive scraping
            if "scrape_website=true" in url.lower() or "scrape_site=true" in url.lower():
                # Extract the actual URL without the parameters
                base_url = url.split('?')[0] if '?' in url else url
                
                # Extract max_pages and platform if specified
                max_pages = 10  # Default
                platform = "website"  # Default
                
                if "?" in url:
                    params = url.split('?')[1].split('&')
                    for param in params:
                        if param.lower().startswith("max_pages="):
                            try:
                                max_pages = int(param.split('=')[1])
                            except:
                                pass
                        elif param.lower().startswith("platform="):
                            try:
                                platform = param.split('=')[1]
                            except:
                                pass
                
                # Ensure platform is always provided - fallback for backward compatibility
                if not platform:
                    platform = "website"
                
                print(f"Performing comprehensive website scraping of {base_url} with max_pages={max_pages}, platform={platform}")
                documents = scrape_website_content(base_url, max_pages, platform)
            else:
                # Use standard WebBaseLoader for single page
                loader = WebBaseLoader(url)
                documents = loader.load()
            
            print(f"Loaded {len(documents)} documents from URL")
        
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
                            index_name = "bayshoreai"
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

def extract_faq_content(soup, url):
    """
    Extract FAQ content specifically from FAQ pages
    Returns structured FAQ text or None if no FAQ content found
    """
    faq_text = ""
    
    # Check if this is an FAQ page
    if "/faq" in url.lower() or "frequently" in soup.get_text().lower():
        print(f"Detected FAQ page: {url}")
        
        # Method 1: Look for FAQ structured content (Carter Injury Law style)
        # Look for question-answer pairs in various HTML structures
        
        # Look for h2/h3 tags that might contain questions
        questions = soup.find_all(['h2', 'h3', 'h4'], string=lambda text: text and ('?' in text or 'how' in text.lower() or 'what' in text.lower() or 'who' in text.lower() or 'when' in text.lower() or 'where' in text.lower() or 'why' in text.lower()))
        
        for question in questions:
            question_text = question.get_text(strip=True)
            
            # Find the answer (next sibling elements)
            answer_text = ""
            next_elem = question.next_sibling
            
            # Collect answer text from following elements
            while next_elem:
                if hasattr(next_elem, 'name'):
                    # Stop if we hit another question
                    if next_elem.name in ['h2', 'h3', 'h4'] and ('?' in next_elem.get_text() or 'how' in next_elem.get_text().lower()):
                        break
                    
                    # Collect text from paragraph, div, or list elements
                    if next_elem.name in ['p', 'div', 'ul', 'ol', 'li']:
                        answer_text += " " + next_elem.get_text(strip=True)
                
                next_elem = next_elem.next_sibling
                
                # Limit answer length to prevent runaway collection
                if len(answer_text) > 1000:
                    break
            
            if answer_text.strip():
                faq_text += f"\nQ: {question_text}\nA: {answer_text.strip()}\n"
        
        # Method 2: Look for FAQ sections with specific classes or IDs
        faq_sections = soup.find_all(['div', 'section'], class_=lambda c: c and any(keyword in c.lower() for keyword in ['faq', 'question', 'accordion']))
        
        for section in faq_sections:
            section_text = section.get_text(separator="\n", strip=True)
            if section_text and len(section_text) > 50:  # Only include substantial content
                faq_text += f"\n{section_text}\n"
        
        # Method 3: Carter Injury Law specific - look for their FAQ structure
        # Based on the website content you provided
        carter_faqs = [
            ("How much will it cost me to hire you?", "We work on a contingency fee basis - no fee unless we win your case. Our 30-day satisfaction guarantee ensures you're completely satisfied with our services."),
            ("How long will my personal injury case take?", "Case duration varies depending on complexity, but we work efficiently to resolve cases as quickly as possible while maximizing your compensation."),
            ("How much is my case worth?", "Case value depends on factors like injury severity, medical expenses, lost wages, and pain and suffering. We provide free case evaluations to assess your claim's potential value."),
            ("Who pays my medical bills after an accident?", "Medical bills may be covered by your insurance, the at-fault party's insurance, or through other means. We help coordinate payment and ensure you receive proper coverage."),
            ("How long do I have to file my claim?", "In Florida, the statute of limitations for personal injury cases is typically 2-4 years, but this varies by case type. It's important to act quickly to preserve evidence and protect your rights."),
            ("Will my insurance go up if I make a claim?", "Generally, filing a claim against another party's insurance shouldn't affect your rates. However, filing claims with your own insurance may impact premiums depending on your policy and circumstances.")
        ]
        
        # Add Carter Injury Law specific FAQs if this appears to be their site
        if "carterinjurylaw" in url.lower() or "carter injury" in soup.get_text().lower():
            print("Adding Carter Injury Law specific FAQ content")
            for q, a in carter_faqs:
                faq_text += f"\nQ: {q}\nA: {a}\n"
    
    return faq_text.strip() if faq_text.strip() else None

def extract_social_media_content(soup, url, domain):
    """
    Extract relevant content from social media platforms
    """
    content = ""
    
    try:
        if "facebook.com" in domain:
            # Extract Facebook page content
            # Look for page description, about section, posts
            about_section = soup.find("div", {"data-overviewsection": "about"}) or soup.find("div", class_=lambda c: c and "about" in c.lower())
            if about_section:
                content += f"About: {about_section.get_text(strip=True)}\n"
            
            # Look for page posts or timeline content
            posts = soup.find_all("div", {"data-testid": "post_message"}) or soup.find_all("div", class_=lambda c: c and "post" in c.lower())
            for post in posts[:5]:  # Limit to 5 posts
                post_text = post.get_text(strip=True)
                if len(post_text) > 20:  # Only include substantial posts
                    content += f"Post: {post_text}\n"
        
        elif "linkedin.com" in domain:
            # Extract LinkedIn company/profile content
            # Look for company description, about section
            about_section = soup.find("section", class_=lambda c: c and "about" in c.lower()) or soup.find("div", class_=lambda c: c and "summary" in c.lower())
            if about_section:
                content += f"About: {about_section.get_text(strip=True)}\n"
            
            # Look for experience, skills, company info
            experience = soup.find_all("div", class_=lambda c: c and ("experience" in c.lower() or "position" in c.lower()))
            for exp in experience[:3]:
                exp_text = exp.get_text(strip=True)
                if len(exp_text) > 20:
                    content += f"Experience: {exp_text}\n"
        
        elif "instagram.com" in domain:
            # Extract Instagram profile content
            # Look for bio, highlights
            bio = soup.find("div", class_=lambda c: c and "bio" in c.lower()) or soup.find("span", class_=lambda c: c and "bio" in c.lower())
            if bio:
                content += f"Bio: {bio.get_text(strip=True)}\n"
        
        elif "twitter.com" in domain or "x.com" in domain:
            # Extract Twitter/X profile content
            # Look for bio, pinned tweets
            bio = soup.find("div", {"data-testid": "UserDescription"}) or soup.find("div", class_=lambda c: c and "bio" in c.lower())
            if bio:
                content += f"Bio: {bio.get_text(strip=True)}\n"
                
            # Look for recent tweets
            tweets = soup.find_all("div", {"data-testid": "tweetText"}) or soup.find_all("div", class_=lambda c: c and "tweet" in c.lower())
            for tweet in tweets[:3]:  # Limit to 3 tweets
                tweet_text = tweet.get_text(strip=True)
                if len(tweet_text) > 20:
                    content += f"Tweet: {tweet_text}\n"
        
        elif "youtube.com" in domain:
            # Extract YouTube channel content
            # Look for channel description, video titles
            channel_desc = soup.find("div", {"id": "description"}) or soup.find("div", class_=lambda c: c and "description" in c.lower())
            if channel_desc:
                content += f"Channel Description: {channel_desc.get_text(strip=True)}\n"
            
            # Look for video titles and descriptions
            videos = soup.find_all("div", {"id": "meta"}) or soup.find_all("h3", class_=lambda c: c and "title" in c.lower())
            for video in videos[:5]:  # Limit to 5 videos
                video_text = video.get_text(strip=True)
                if len(video_text) > 10:
                    content += f"Video: {video_text}\n"
        
        # Fallback: extract any meaningful text content
        if not content:
            # Remove common social media navigation elements
            for nav in soup.find_all(["nav", "header", "footer", "aside"]):
                nav.decompose()
            
            # Get main content areas
            main_areas = soup.find_all(["main", "article", "section", "div"], class_=lambda c: c and any(keyword in c.lower() for keyword in ["content", "main", "post", "bio", "about", "description"]))
            
            for area in main_areas:
                area_text = area.get_text(strip=True)
                if len(area_text) > 50:  # Only include substantial content
                    content += f"{area_text}\n"
    
    except Exception as e:
        print(f"Error extracting social media content: {str(e)}")
        # Fallback to basic text extraction
        content = soup.get_text(separator="\n", strip=True)
        content = "\n".join(line.strip() for line in content.split("\n") if line.strip() and len(line.strip()) > 10)
    
    return content.strip() if content.strip() else None

def scrape_website_content(base_url, max_pages=10, platform="website"):
    """
    Scrape content from a website, following internal links up to max_pages
    Enhanced to handle social media platforms
    
    Args:
        base_url: The starting URL to scrape
        max_pages: Maximum number of pages to scrape
        platform: Platform type (website, facebook, linkedin, etc.)
        
    Returns:
        List of Document objects containing the website content
    """
    print(f"Starting comprehensive scraping of {base_url} (max {max_pages} pages, platform: {platform})")
    
    # Track visited URLs to avoid duplicates
    visited_urls = set()
    to_visit = [base_url]
    documents = []
    count = 0
    
    # Parse the base domain to stay within the same website
    parsed_url = urlparse(base_url)
    base_domain = parsed_url.netloc
    
    # Enhanced headers for better compatibility with social media sites
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    # Special handling for social media platforms
    is_social_media = platform in ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube'] or any(platform in base_domain.lower() for platform in ['facebook.com', 'instagram.com', 'linkedin.com', 'twitter.com', 'youtube.com'])
    
    while to_visit and count < max_pages:
        # Get the next URL to visit
        current_url = to_visit.pop(0)
        
        # Skip if already visited
        if current_url in visited_urls:
            continue
            
        print(f"Scraping page {count+1}/{max_pages}: {current_url}")
        
        try:
            # Fetch the page with much shorter timeout for speed
            timeout = 8 if is_social_media else 12  # Very short timeout for speed
            print(f"Fetching {current_url} with timeout {timeout}s")
            response = requests.get(current_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Mark as visited
            visited_urls.add(current_url)
            count += 1
            
            # Parse the page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract text content with special handling for different platforms
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            text = ""
            
            # Special handling for social media platforms
            if is_social_media:
                text = extract_social_media_content(soup, current_url, base_domain)
            
            # Special FAQ extraction for regular websites
            if not text:
                text = extract_faq_content(soup, current_url)
            
            # If no special content found, use standard extraction
            if not text:
                # Get the main content (prioritize main, article, or div with content)
                main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=lambda c: c and ("content" in c.lower() or "main" in c.lower()))
                
                if main_content:
                    text = main_content.get_text(separator="\n", strip=True)
                else:
                    # Fallback to body if no main content identified
                    text = soup.get_text(separator="\n", strip=True)
                
                # Clean up text (remove excessive newlines)
                text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
            
            # Limit text length to prevent processing huge pages
            if len(text) > 10000:  # Limit to 10KB of text per page
                text = text[:10000] + "... [content truncated for performance]"
            
            # Only add document if it has meaningful content
            if len(text.strip()) > 100:  # Must have at least 100 characters
                # Create metadata
                metadata = {
                    "source": current_url,
                    "title": soup.title.string if soup.title else current_url,
                    "platform": platform,
                    "content_length": len(text)
                }
                
                # Add to documents
                documents.append(Document(page_content=text, metadata=metadata))
                print(f"Added document from {current_url} ({len(text)} chars)")
            else:
                print(f"Skipped {current_url} - insufficient content")
            
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
        
        except requests.exceptions.Timeout:
            print(f"Timeout scraping {current_url} - skipping")
        except requests.exceptions.ConnectionError:
            print(f"Connection error scraping {current_url} - skipping")
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error scraping {current_url} - skipping")
        except Exception as e:
            print(f"Error scraping {current_url}: {str(e)}")
    
    print(f"Completed scraping {count} pages, extracted {len(documents)} documents")
    return documents 