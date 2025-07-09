# sol_flask.py

# --- IMPORTS ---
import os
import io
import time
import json  # For loading credentials from env
import logging
import threading
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from groq import Groq
from dotenv import load_dotenv
import requests
import chromadb
from chromadb.utils import embedding_functions
from bs4 import BeautifulSoup
import markdownify  # GafComment: Convert Markdown to HTML using markdownify

# Optional OpenCLIP import for image embeddings
try:
    from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "OpenCLIPEmbeddingFunction not available: install open-clip-torch to enable image context."
    )

# Google Drive API imports for RAG
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- LOAD ENV ---
load_dotenv()  # Loads SOL_GPT_PASSWORD, BRAVE_API_KEY, GROQ_API_KEY, DRIVE_CRED_JSON, DRIVE_FOLDER_ID

# --- CONFIGURE LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG & CLIENTS ---
# Required env vars
required_vars = ["SOL_GPT_PASSWORD", "BRAVE_API_KEY", "GROQ_API_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient()
text_collection = chroma_client.get_or_create_collection(
    "sol_docs",
    embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

# Google Drive setup for RAG (optional)
drive_service = None
FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
_creds_json = os.getenv("DRIVE_CRED_JSON")
if _creds_json and FOLDER_ID:
    try:
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
        info = json.loads(_creds_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        drive_service = build("drive", "v3", credentials=creds)
        logger.info("Google Drive RAG enabled.")
    except Exception as e:
        drive_service = None
        logger.warning(f"Google Drive credentials not loaded: {e}")
else:
    logger.info("Google Drive RAG disabled (missing JSON creds or folder ID).")

# --- TEXT SPLITTER ---
def split_text(text, chunk_size=1000, chunk_overlap=200):
    docs = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        docs.append(text[start:end])
        start += chunk_size - chunk_overlap
    return docs

# --- DRIVE INDEXER ---
def load_drive_docs():
    if not drive_service:
        return
    try:
        resp = drive_service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed = false",
            fields="files(id,name,mimeType)"
        ).execute()
        files = resp.get("files", [])
    except Exception as e:
        logger.error(f"Failed to list Drive files: {e}")
        return
    for f in files:
        try:
            fid, name, mime = f['id'], f['name'], f['mimeType']
            if mime == 'application/vnd.google-apps.document':
                request_obj = drive_service.files().export_media(fileId=fid, mimeType='text/plain')
            else:
                request_obj = drive_service.files().get_media(fileId=fid)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request_obj)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            text = fh.getvalue().decode('utf-8', errors='ignore')
            docs = split_text(text)
            embeddings = [embedding_functions.DefaultEmbeddingFunction()(d) for d in docs]
            text_collection.add(
                embeddings=embeddings,
                documents=docs,
                metadatas=[{"source": name}] * len(docs)
            )
            logger.info(f"Indexed Drive file: {name} ({len(docs)} chunks)")
        except Exception as ex:
            logger.warning(f"Failed to index {name}: {ex}")

threading.Thread(target=load_drive_docs, daemon=True).start()

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """You are Sol: a locally hosted AI assistant built specifically for Gaf (Bryan Gaffin)..."""

# --- PRE-FETCH UI TEMPLATE ---
try:
    ui_resp = requests.get("https://gaf.nyc/sol.html", timeout=5)
    page_html = ui_resp.text
except Exception as e:
    logger.warning(f"Failed to fetch UI template: {e}")
    try:
        page_html = open(os.path.join(os.getcwd(), 'templates', 'sol.html')).read()
    except Exception:
        page_html = "<!-- sol.html unavailable -->"

# --- HELPERS ---
def brave_search(query):
    headers = {"Accept": "application/json", "X-Subscription-Token": os.getenv("BRAVE_API_KEY")}  
    params = {"q": query[:200], "count": 5, "freshness": "day"}
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers, params=params, timeout=5
        )
        resp.raise_for_status()
        items = resp.json().get("web", {}).get("results", []) or []
        return [{"title": i.get("title"), "url": i.get("url"), "description": i.get("description")} for i in items]
    except Exception as e:
        logger.error(f"Brave search failed: {e}")
        return []

def format_brave_html(results):
    lines = []
    for idx, r in enumerate(results, start=1):
        lines.append(
            f"<p><strong>[{idx}] <a href='"{r['url']}"' target='_blank' rel='noopener'>" +
            f"{r['title']}</a></strong><br>{r['description']}</p>"
        )
    return "".join(lines)

# --- FLASK APP SETUP ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def password_gate():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == os.getenv('SOL_GPT_PASSWORD'):
            session['authenticated'] = True
            return redirect(url_for('sol_home'))
    return render_template('index.html')

@app.route('/chat', methods=['GET', 'POST'])
def sol_home():
    if request.method == 'GET':
        return page_html, 200

    # Authentication guard
    if not session.get('authenticated'):
        return jsonify({"error": "Not authenticated"}), 401

    user_msg = request.form.get('message', '').strip()
    # Skip citations for casual greetings
    greetings = {'hi', 'hello', 'hey'}
    first_word = user_msg.lower().split()[0] if user_msg else ''
    casual = first_word in greetings and len(user_msg.split()) <= 2

    uploaded_file = request.files.get('file')

    history = session.setdefault('history', [])
    history.append({'role': 'user', 'content': user_msg})
    session['history'] = history[-20:]

    drive_contexts, drive_sources = [], []
    if drive_service and not casual:
        try:
            res = text_collection.query(query_texts=[user_msg], n_results=3)
            docs, metas = res.get('documents')[0], res.get('metadatas')[0]
            for d, m in zip(docs, metas):
                drive_contexts.append(d)
                drive_sources.append(m.get('source'))
        except Exception as e:
            logger.warning(f"Drive RAG failed: {e}")

    image_context, image_source = '', None
    if uploaded_file and CLIP_AVAILABLE and not casual:
        try:
            img_data = uploaded_file.read()
            clip_fn = OpenCLIPEmbeddingFunction()
            emb = clip_fn(img_data)
            res = text_collection.query(query_embeddings=[emb], n_results=1)
            image_context = res.get('documents')[0][0]
            image_source = res.get('metadatas')[0][0].get('source')
        except Exception as e:
            logger.warning(f"Image RAG failed: {e}")

    brave_html = ''
    if not casual:
        brave_results = brave_search(user_msg)
        brave_html = format_brave_html(brave_results)
    else:
        brave_results = []

    parts = [user_msg]
    if drive_contexts:
        parts.append('Drive Context:\n\n' + '\n\n'.join(f'[{i+1}] {c}' for i, c in enumerate(drive_contexts)))
    if image_context:
        parts.append(f'Image Context from [{image_source}]:\n{image_context}')
    if brave_results:
        parts.append('Web Search Results:')
    prompt_text = '\n\n'.join(parts)

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + session['history']

    start = time.time()
    try:
        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}"},
                'Content-Type': 'application/json'},
            json={
                'model': 'llama3-8b-8192',
                'messages': messages,
                'temperature': 0.6
            },
            timeout=30
        )
        resp.raise_for_status()
        reply_md = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return jsonify({'reply': '⚠️ Error', 'duration': '[]', 'html': page_html}), 500
    duration = time.time() - start

    session['history'] = (session['history'] + [{'role': 'assistant', 'content': reply_md}])[-20:]

    reply_html = markdownify.markdownify(reply_md, heading_style="ATX")
    sources_html = []
    if not casual:
        if drive_sources:
            sources_html.append('<h4>Drive Sources</h4>' + '<br>'.join(f'[{i+1}] {s}' for i, s in enumerate(drive_sources)))
        if image_source:
            sources_html.append(f'<h4>Image Source</h4>[{image_source}]')
        if brave_html:
            sources_html.append(f'<h4>Web Sources</h4>{brave_html}')
    structured_html = reply_html + ('<hr>' + ''.join(sources_html) if sources_html else '')

    return jsonify({'reply': structured_html, 'duration': f"[{duration:.2f}s]", 'html': page_html})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)  # GafComment: Launch on port 10000, debug off for prod
