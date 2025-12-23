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

# LLM Settings
LLM_TEMPERATURE = 0.4
LLM_MAX_TOKENS = 600

# RAG Settings
RAG_TOP_K = 5
RAG_SIMILARITY_THRESHOLD = 0.25
RAG_MAX_HISTORY_TURNS = 10
