# config.py  (or wherever you keep your bootstrap code)

import os
import json
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 1) Load .env
load_dotenv()

# 2) Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 3) Required secrets
required = ["SOL_GPT_PASSWORD", "GROQ_API_KEY"]
missing = [v for v in required if not os.getenv(v)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {missing}")

# 4) Optional Brave Search key
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
if BRAVE_API_KEY:
    logger.info("Brave Search enabled.")
else:
    logger.info("Brave Search disabled (no BRAVE_API_KEY).")

def search_brave(query: str, count: int = 5):
    """
    Returns a list of (title, snippet, url) from Brave Search.
    Falls back to empty list if no key/config.
    """
    if not BRAVE_API_KEY:
        return []

    import requests
    endpoint = "https://api.search.brave.com/res/v1/web/all"
    headers = {
        "Accept": "application/json",
        "X-API-KEY": BRAVE_API_KEY,
    }
    params = {"q": query, "size": count}
    r = requests.get(endpoint, headers=headers, params=params, timeout=5)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("data", []):
        results.append((item.get("title"), item.get("description"), item.get("url")))
    return results

# 5) Initialize Groq + Chroma
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
    logger.info("Groq & ChromaDB initialized.")
except Exception as e:
    logger.warning(f"Groq/Chroma init failed: {e}")
    client = None
    chroma_client = None
    text_collection = None

# 6) Google Drive RAG
drive_service = None
FOLDER_ID      = os.getenv("DRIVE_FOLDER_ID")
creds_json     = os.getenv("DRIVE_CRED_JSON")
creds_path     = os.getenv("DRIVE_CRED_PATH")

if FOLDER_ID and (creds_json or creds_path):
    try:
        if creds_json:
            info = json.loads(creds_json)
        else:
            with open(creds_path, "r", encoding="utf-8") as f:
                info = json.load(f)

        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.file"
            ],
        )
        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info("Google Drive RAG enabled.")
    except Exception as e:
        drive_service = None
        logger.warning(f"Google Drive RAG disabled: {e}")
else:
    logger.info("Google Drive RAG disabled (missing FOLDER_ID or credentials).")

# 7) System prompt
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are Sol: a locally hosted AI assistant built specifically for Gaf."
)

# 8) Helper to load docs (if you have rag.drive.load_drive_docs)
from rag.drive import load_drive_docs
def get_drive_snippets():
    if not drive_service:
        return []
    docs = load_drive_docs(drive_service, FOLDER_ID)
    # load_drive_docs may return (docs, metadata) or just docs
    docs_list = docs[0] if isinstance(docs, tuple) else docs
    return [d.page_content if hasattr(d, "page_content") else str(d)
            for d in docs_list[:3]]

