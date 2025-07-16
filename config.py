import os
import json
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()  # Loads SOL_GPT_PASSWORD, BRAVE_API_KEY, GROQ_API_KEY, DRIVE_CRED_JSON, DRIVE_CRED_PATH, DRIVE_FOLDER_ID

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate required env vars
required_vars = ["SOL_GPT_PASSWORD", "BRAVE_API_KEY", "GROQ_API_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

# Initialize Groq client and ChromaDB
try:
    from groq import Groq
    import chromadb
    from chromadb.utils import embedding_functions

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    chroma_client = chromadb.PersistentClient()
    text_collection = chroma_client.get_or_create_collection(
        "sol_docs",
        embedding_function=embedding_functions.DefaultEmbeddingFunction()
    )
    logger.info("Groq and Chroma initialized.")
except Exception as e:
    logger.warning(f"Failed to initialize Groq/Chroma: {e}")
    client = None
    chroma_client = None
    text_collection = None

# Optional Google Drive RAG setup
drive_service = None
FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
creds_json = os.getenv("DRIVE_CRED_JSON")
creds_path = os.getenv("DRIVE_CRED_PATH")
if FOLDER_ID and (creds_json or creds_path):
    try:
        if creds_json:
            info = json.loads(creds_json)
        else:
            with open(creds_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        drive_service = build("drive", "v3", credentials=creds)
        logger.info("Google Drive RAG enabled.")
    except Exception as e:
        drive_service = None
        logger.warning(f"Google Drive RAG disabled: {e}")
else:
    logger.info("Google Drive RAG disabled (missing folder ID or credentials)")

# System prompt placeholder
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are Sol: a locally hosted AI assistant built specifically for Gaf.")
