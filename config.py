# config.py

import os
import json
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ─── 1) Load .env & personality file ────────────────────────────────
load_dotenv()

# locate your personality prompt on disk
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "SYSTEMPROMPT.txt"), encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

# ─── 2) Logging ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── 3) Validate core env vars ──────────────────────────────────────
required = ["SOL_GPT_PASSWORD", "GROQ_API_KEY"]
missing  = [v for v in required if not os.getenv(v)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {missing}")

# ─── 4) Optional Brave Search ───────────────────────────────────────
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
if BRAVE_API_KEY:
    logger.info("Brave Search enabled.")
else:
    logger.info("Brave Search disabled.")

# ─── 5) Initialize Groq & Chroma ────────────────────────────────────
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

# ─── 6) Google Drive & Vision credentials ────────────────────────────
drive_service    = None
GCP_CREDENTIALS  = None

FOLDER_ID  = os.getenv("DRIVE_FOLDER_ID")
creds_json = os.getenv("DRIVE_CRED_JSON")
creds_path = os.getenv("DRIVE_CRED_PATH")

if FOLDER_ID and (creds_json or creds_path):
    try:
        # load service-account info
        if creds_json:
            info = json.loads(creds_json)
        else:
            with open(creds_path, "r", encoding="utf-8") as f:
                info = json.load(f)

        # request full Drive R/W + allow all Google Cloud APIs (incl. Vision)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/cloud-platform"
            ],
        )

        # build the Drive service
        drive_service = build(
            "drive", "v3",
            credentials=creds,
            cache_discovery=False
        )

        # stash creds for Vision client usage
        GCP_CREDENTIALS = creds

        logger.info("Google Drive & Vision credentials initialized.")
    except Exception as e:
        logger.warning(f"Google Drive RAG disabled: {e}")
else:
    logger.info("Google Drive RAG disabled (missing FOLDER_ID or credentials).")

# ─── 7) Expose any helpers ───────────────────────────────────────────
from rag.drive import load_drive_docs

def get_drive_snippets():
    """Return up to 3 page_content strings from your Drive-folder docs."""
    if not drive_service:
        return []
    docs = load_drive_docs(drive_service, FOLDER_ID)
    docs_list = docs[0] if isinstance(docs, tuple) else docs
    snippets = []
    for d in docs_list[:3]:
        snippets.append(getattr(d, "page_content", str(d)))
    return snippets
