# sol_app.py

# --- IMPORTS ---
from flask import Flask, request, jsonify, render_template, redirect, url_for, session  # GafComment: Removed render_template_string
from groq import Groq  # GafComment: Correct client import
import os
import time
import base64
import io
import requests  # GafComment: Single import for HTTP
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from bs4 import BeautifulSoup
import markdownify

# Google Drive API imports for RAG
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# If using a text splitter library; otherwise implement your own
from langchain.text_splitter import RecursiveCharacterTextSplitter  # GafComment: For splitting docs

# --- LOAD ENV ---
load_dotenv()  # GafComment: Loads SOL_GPT_PASSWORD, BRAVE_API_KEY, GROQ_API_KEY, DRIVE_CRED_PATH, DRIVE_FOLDER_ID

# --- CONFIG & CLIENTS ---
# Validate required env vars
for var in ("SOL_GPT_PASSWORD", "BRAVE_API_KEY", "GROQ_API_KEY", "DRIVE_CRED_PATH", "DRIVE_FOLDER_ID"):
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

# Google Drive setup for RAG
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE = os.getenv("DRIVE_CRED_PATH")
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=creds)
FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

# Function to load and index Drive docs
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
def load_drive_docs():
    resp = drive_service.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed = false",
        fields="files(id,name,mimeType)"
    ).execute()
    for f in resp.get("files", []):
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
        docs = splitter.split_text(text)
        embeddings = [embedding_functions.DefaultEmbeddingFunction()(d) for d in docs]
        text_collection.add(
            embeddings=embeddings,
            documents=docs,
            metadatas=[{"source": name}] * len(docs)
        )
load_drive_docs()

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
    page_html = f"<!-- sol.html fetch error: {e} -->"

# --- HELPERS ---
def brave_search(query):
    headers = {"Accept": "application/json", "X-Subscription-Token": os.getenv("BRAVE_API_KEY")}  # GafComment: Use GET
    params = {"q": query, "count": 5, "freshness": "day"}
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=5
        )
        resp.raise_for_status()
        results = [
            f"{i+1}. {item.get('title','')} — {item.get('url','')}\n{item.get('description','')}"
            for i, item in enumerate(resp.json().get("web", {}).get("results", []))
        ]
        return "\n\n".join(results)
    except Exception as e:
        return f"Web search error: {e}"

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
    if request.method == "GET":  # Serve UI
        return page_html, 200
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    user_msg = request.form.get("message", "").strip()
    uploaded_file = request.files.get("file")
    context = ""

    session.setdefault("history", [])

    # Drive RAG context
    drive_res = text_collection.query(query_texts=[user_msg], n_results=3)
    drive_context = "\n\n".join(
        f"[{m['source']}] {d}" for d, m in zip(drive_res["documents"][0], drive_res["metadatas"][0])
    )

    # Image context
    if uploaded_file:
        img_data = uploaded_file.read()
        clip_fn = embedding_functions.OpenCLIPEmbeddingFunction()
        embedding = clip_fn(img_data)
        img_res = text_collection.query(query_embeddings=[embedding], n_results=1)
        context = img_res.get("documents", [[""]])[0][0]

    brave_results = brave_search(user_msg)

    content = (
        f"{user_msg}\n\n"
        f"Drive Context:\n{drive_context}\n\n"
        f"Image Context:\n{context}\n\n"
        f"Web Search:\n{brave_results}"
    )

    session["history"].append({"role": "user", "content": content})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session["history"]

    start_time = time.time()
    try:
        groq_resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}", "Content-Type": "application/json"},
            json={"model": "llama3-8b-8192", "messages": messages, "temperature": 0.6},
            timeout=30
        )
        groq_resp.raise_for_status()
        reply_raw = groq_resp.json()["choices"][0]["message"]["content"]
        duration = time.time() - start_time

        session["history"].append({"role": "assistant", "content": reply_raw})

        htmlified = markdownify.markdownify(reply_raw, heading_style="ATX")
        soup = BeautifulSoup(htmlified, "html.parser")
        for a in soup.find_all("a"):
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

        return jsonify({"reply": soup.decode(), "duration": f"[{duration:.2f}s]", "html": page_html})
    except Exception as e:
        err_duration = time.time() - start_time
        return jsonify({"reply": f"⚠️ Error: {e}", "duration": f"[{err_duration:.2f}s]", "html": page_html}), 500

# --- RUN APP ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)  # GafComment: Launch on port 10000
