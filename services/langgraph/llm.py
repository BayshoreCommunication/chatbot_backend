from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .config import OPENAI_API_KEY, EMBEDDING_MODEL, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

# Initialize LLM for chat generation
llm = ChatOpenAI(
    model=LLM_MODEL,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
    api_key=OPENAI_API_KEY
)

# Initialize embeddings for vector search
embeddings = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    dimensions=1024,
    api_key=OPENAI_API_KEY
)
