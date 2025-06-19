import logging
import os
from dotenv import load_dotenv

load_dotenv()

def setup_logging():
    """Configure logging levels for all modules to reduce debug noise"""
    
    # Get log level from environment variable, default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Main application logging
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Silence noisy third-party libraries
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('pinecone').setLevel(logging.WARNING)
    logging.getLogger('langchain').setLevel(logging.WARNING)
    logging.getLogger('chromadb').setLevel(logging.WARNING)
    
    # Keep only essential logs
    essential_loggers = [
        'calendly',
        'appointment', 
        'chatbot',
        'auth'
    ]
    
    for logger_name in essential_loggers:
        logging.getLogger(logger_name).setLevel(logging.INFO)
    
    print(f"[LOGGING] Configured logging level: {log_level}")
    print(f"[LOGGING] Essential logs: {', '.join(essential_loggers)}")

# Setup logging when this module is imported
setup_logging() 