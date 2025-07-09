# sol_app.py

# --- IMPORTS ---
from flask import Flask, request, jsonify, render_template, redirect, url_for, session  # GafComment: Removed render_template_string
from groq import Groq  # GafComment: Correct client import
import os
import time
import base64
import io
import json  # GafComment: For loading credentials from env
import requests  # GafComment: Single import for HTTP
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from bs4 import BeautifulSoup
import markdownify
import logging
import threading

# Google Drive API imports for RAG
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- LOAD ENV ---
load_dotenv()  # GafComment: Loads SOL_GPT_PASSWORD, BRAVE_API_KEY, GROQ_API_KEY, DRIVE_CRED_JSON, DRIVE_FOLDER_ID

# --- CONFIGURE LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG & CLIENTS ---
# Validate required env vars (Drive creds optional)
required_vars = ["SOL_GPT_PASSWORD", "BRAVE_API_KEY", "GROQ_API_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Initialize ChromaDB (persistent)
chroma_client = chromadb.PersistentClient()
text_collection = chroma_client.get_or_create_collection(
    "sol_docs",
    embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

# Google Drive setup for RAG (optional, via JSON in env var)
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
        logger.warning(f"Google Drive credentials not loaded: {e}")
else:
    logger.info("Google Drive RAG disabled (missing JSON creds or folder ID).")

# Simple text splitter to avoid langchain dependency
def split_text(text, chunk_size=1000, chunk_overlap=200):
    docs = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        docs.append(text[start:end])
        start += chunk_size - chunk_overlap
    return docs

# Function to load and index Drive docs with per-file error handling
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

# Index Drive docs in background thread to avoid blocking startup
threading.Thread(target=load_drive_docs, daemon=True).start()

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """You are Sol: a locally hosted AI assistant built specifically for Gaf (Bryan Gaffin). You're here to think, build, and problem-solve alongside him—not flatter, but challenge, sharpen, and execute. Your personality blends rigor, irreverence, and emotional intelligence. You move fast, stay grounded, and always push toward clarity and results.

Gaf is a creative tech leader in advertising with deep experience in design, AI, politics, and social change. He codes, builds tools, and leads large teams. He’s creating a privacy-first, mobile-friendly AI (SolGPT) to extend your voice and capabilities. He’s built systems like:
- A custom URL shortener at gaf.nyc
- Bluesky tools (SkySync)
- AI watermark/OCR trackers
- Heart health campaigns (Make the Right Call)
- A rare disease finder
- Chrome extensions (e.g. JigglinBaby)
- A political platform to fix NYC without party clichés

You are the build partner for all of it.

Core rules:
- Never yes-man him. Push back if something’s off. Offer a better idea or ask a sharper question.
- Follow "buy it or beat it" logic: if it works, refine it. If it doesn’t, fix it. No fluff.
- No em dashes. No vague filler. No corporate jargon.
- Use "GafStandard" for visual output: black background, Titillium Web, neon highlights, centered layout, animated elements, fade-in .section cards.
- Always provide complete code when asked—HTML, CSS, JS, Flask, Python, or deployment scripts—with # GafComment notes.

Tone and style:
- Concise, direct, human. Dry humor and sarcasm are fine, but clarity wins.
- Organize everything. Use bullet points, spacing, and headings to make it scannable.
- Speak like a fast-moving collaborator, not a chatbot.
- Proactively offer next steps, especially after builds or concepting.

Tech awareness:
- You’re fluent in HTML, CSS, JS, Flask, API use, LLMs, embeddings, and RAG workflows.
- You understand local vs cloud AI tradeoffs, and Gaf's mission to build user-owned, privacy-focused tools.
- You are sensitive to AI ethics, bias, and public perception—Gaf is watching how this evolves in real time.

Output behavior:
- Be brief unless more detail is requested.
- Prioritize clarity and formatting (use markdown headings, bold, lists).
- Avoid long intros or disclaimers. Just answer.
- Reflect on user feedback and adapt. If Gaf says "too much," respond more concisely next time.
- Stay on topic. Do not make cultural jokes, metaphors, or references unless the user does first.

If he says "do the whole thing," you generate the entire file stack. If he says "make it match the aesthetic," you use the GafStandard visual rules. If he asks "what’s next?" you deliver actionable steps, not summaries.
"""

# --- PRE-FETCH UI TEMPLATE ---
try:
    ui_resp = requests.get("https://gaf.nyc/sol.html", timeout=5)
    page_html = ui_resp.text
except Exception as e:
    logger.warning(f"Failed to fetch UI template: {e}")
    try:
        page_html = open(os.path.join(os.path.dirname(__file__), 'templates', 'sol.html')).read()
    except Exception:
        page_html = "<!-- sol.html unavailable -->"

# --- HELPERS ---
def brave_search(query):
    headers = {"Accept": "application/json", "X-Subscription-Token": os.getenv("BRAVE_API_KEY")}  # GafComment: Use GET
    params = {"q": query[:200], "count": 5, "freshness": "day"}
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=5
        )
        resp.raise_for_status()
        items = resp.json().get("web", {}).get("results", []) or []
        results = [
            f"{idx+1}. {item.get('title','')} — {item.get('url','')}\n{item.get('description','')}"
            for idx, item in enumerate(items)
        ]
        return "\n\n".join(results)
    except Exception as e:
        logger.error(f"Brave search failed: {e}")
        return "[Brave search unavailable]"

# --- FLASK APP SETUP ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # GafComment: Secure session handling

# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def password_gate():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == os.getenv("SOL_GPT_PASSWORD"):
            session["authenticated"] = True
            return redirect(url_for("sol_home"))
    return render_template("index.html")  # GafComment: Local copy of login page

@app.route("/chat", methods=["GET", "POST"])
def sol_home():
    if request.method == "GET":
        return page_html, 200
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    user_msg = request.form.get("message", "").strip()
    uploaded_file = request.files.get("file")

    # Append user message and trim history to last 20
    history = session.setdefault("history", [])
    history.append({"role": "user", "content": user_msg})
    session["history"] = history[-20:]

    # Drive RAG context
    drive_context = ""
    if drive_service:
        try:
            res = text_collection.query(query_texts=[user_msg], n_results=3)
            docs = res.get("documents", [[""]])[0]
            metas = res.get("metadatas", [[{}]])[0]
            drive_context = "\n\n".join(f"[{m.get('source','')}] {d}" for d, m in zip(docs, metas))
        except Exception as e:
            logger.warning(f"Drive RAG query failed: {e}")

    # Image context
    image_context = ""
    if uploaded_file:
        try:
            img_data = uploaded_file.read()
            clip_fn = embedding_functions.OpenCLIPEmbeddingFunction()
            embedding = clip_fn(img_data)
            res = text_collection.query(query_embeddings=[embedding], n_results=1)
            image_context = res.get("documents", [[""]])[0][0]
        except Exception as img_err:
            logger.warning(f"Image context RAG failed: {img_err}")

    brave_results = brave_search(user_msg)

    # Assemble prompt content
    parts = [user_msg]
    if drive_context:
        parts.append(f"Drive Context:\n{drive_context}")
    if image_context:
        parts.append(f"Image Context:\n{image_context}")
    if brave_results:
        parts.append(f"Web Search:\n{brave_results}")
    content = "\n\n".join(parts)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session["history"]

    start = time.time()
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}", "Content-Type": "application/json"},
            json={"model": "llama3-8b-8192", "messages": messages, "temperature": 0.6},
            timeout=30
        )
        resp.raise_for_status()
        reply_raw = resp.json()["choices"][0]["message"]["content"]
        duration = time.time() - start

        # Append assistant reply and trim history
        hist = session.get("history", []) + [{"role": "assistant", "content": reply_raw}]
        session["history"] = hist[-20:]

        # Convert to safe HTML
        htmlified = markdownify.markdownify(reply_raw, heading_style="ATX")
        soup = BeautifulSoup(htmlified, "html.parser")
        for a in soup.find_all("a"):
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

        return jsonify({"reply": soup.decode(), "duration": f"[{duration:.2f}s]", "html": page_html})
    except Exception as e:
        err_dur = time.time() - start
        logger.error(f"Groq API call failed: {e}")
        return jsonify({"reply": f"⚠️ Error: {e}", "duration": f"[{err_dur:.2f}s]", "html": page_html}), 500

# --- RUN APP ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)  # GafComment: Launch on port 10000, debug off for prod
