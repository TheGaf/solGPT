import os
from dotenv import load_dotenv
import logging

# Optional imports for dependencies
try:
    from groq import Groq
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    Groq = None
    chromadb = None
    embedding_functions = None

load_dotenv()  # Load environment variables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
