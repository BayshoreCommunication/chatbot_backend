import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Pinecone Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "bayai")

# LLM Settings - Optimized for Speed & Quality
LLM_TEMPERATURE = 0.3  # Lower for faster, more consistent responses
LLM_MAX_TOKENS = 350  # Reduced for faster responses (still 2-3 sentences)

# RAG Settings - Optimized for Speed
RAG_TOP_K = 3  # Reduced from 5 to 3 for faster retrieval
RAG_SIMILARITY_THRESHOLD = 0.40  # Higher threshold = better quality, faster processing
RAG_MAX_HISTORY_TURNS = 10  # Reduced from 30 for faster context processing
