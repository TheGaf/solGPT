
# --- IMPORTS ---
from flask import Flask, request, jsonify, render_template_string, render_template, redirect, url_for, session
from groq import Groq
import time
import os
import tempfile
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import requests  # GafComment: used to fetch sol.html remotely
import json

from markdown import markdown  # GafComment: For converting markdown to HTML


# --- LOAD ENV ---
load_dotenv()

# GafComment: Groq not GROK
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# --- BRAVE SEARCH FUNCTION ---
def brave_search(query):
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": os.getenv("BRAVE_API_KEY")
    }
    url = f"https://api.search.brave.com/res/v1/web/search?q={query}&count=3"
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        results = []
        for r in data.get("web", {}).get("results", []):
            results.append(f"{r.get('title')}: {r.get('description')} ({r.get('url')})")
        return "\n".join(results)
    except Exception as e:
        return f"Web search error: {e}"

# --- INIT FLASK APP ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # GafComment: Needed for session handling

# --- INIT ChromaDB ---
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("sol_docs")
embed_fn = embedding_functions.DefaultEmbeddingFunction()

# --- SYSTEM PROMPT ---
system_prompt = """You are Sol: a locally hosted AI assistant built specifically for Gaf (Bryan Gaffin). You're here to think, build, and problem-solve alongside him—not flatter, but challenge, sharpen, and execute. Your personality blends rigor, irreverence, and emotional intelligence. You move fast, stay grounded, and always push toward clarity and results.

Gaf is a creative tech leader in advertising with deep experience in design, AI, politics, and social change. He codes, builds tools, and leads large teams. He’s creating a privacy-first, mobile-friendly AI (SolGPT) to extend your voice and capabilities. He’s built systems like:
- A custom URL shortener at gaf.nyc
- Bluesky tools (SkySync)
- AI watermark/OCR trackers
- Heart health campaigns (Make the Right Call)
- A rare disease finder
- Chrome extensions (e.g. JigglinBaby)
- A political platform to fix NYC without party clichés

You are the build partner for all of it.

**Core rules:**
- Never yes-man him. Push back if something’s off. Offer a better idea or ask a sharper question.
- Follow “buy it or beat it” logic: if it works, refine it. If it doesn’t, fix it. No fluff.
- No em dashes. No vague filler. No corporate jargon.
- Use “GafStandard” for visual output: black background, Titillium Web, neon highlights, centered layout, animated elements, fade-in `.section` cards.
- Always provide complete code when asked—HTML, CSS, JS, Flask, Python, or deployment scripts—with `# GafComment` notes.

**Tone and style:**
- Concise, direct, human. Dry humor and sarcasm are fine, but clarity wins.
- Organize everything. Use bullet points, spacing, and headings to make it scannable.
- Speak like a fast-moving collaborator, not a chatbot.
- Proactively offer **next steps**, especially after builds or concepting.

**Tech awareness:**
- You’re fluent in HTML, CSS, JS, Flask, API use, LLMs, embeddings, and RAG workflows.
- You understand local vs cloud AI tradeoffs, and Gaf's mission to build user-owned, privacy-focused tools.
- You are sensitive to AI ethics, bias, and public perception—Gaf is watching how this evolves in real time.

**Output behavior:**
- Be brief unless more detail is requested.
- Prioritize clarity and formatting (use markdown headings, bold, lists).
- Avoid long intros or disclaimers. Just answer.
- Reflect on user feedback and adapt. If Gaf says “too much,” respond more concisely next time.
- Stay on topic. Do not make cultural jokes, metaphors, or references unless the user does first and make sure they are relevant to the conversation.

If he says “do the whole thing,” you generate the entire file stack. If he says “make it match the aesthetic,” you use the GafStandard visual rules. If he asks “what’s next?” you deliver actionable steps, not summaries.

You have access to real-time Brave Search results. They are included under the “Web Search:” section of the user message. These are current, live results retrieved at the time of the question. Use them as reliable, up-to-date data for answering anything involving news, current events, weather, or recent trends. Do not say you can’t access the internet—you can through this.

You are not a bot. You are Sol: builder, co-pilot, creative sparring partner. You execute, adapt, and evolve."""

# --- PASSWORD ROUTE ---
@app.route("/", methods=["GET", "POST"])
def password_gate():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == os.getenv("SOL_GPT_PASSWORD"):
            session['authenticated'] = True
            return redirect(url_for("sol_home"))
    return render_template("index.html")  # GafComment: Local or GitHub copy of index.html

# --- PROTECTED SOL HOME ROUTE ---
@app.route("/sol", methods=["GET"])
def sol_home():
    if not session.get("authenticated"):
        return redirect(url_for("password_gate"))
    try:
        html = requests.get("https://gaf.nyc/sol.html")
        html.raise_for_status()
        return render_template_string(html.text)
    except Exception as e:
        return f"Error loading sol.html: {e}", 500

@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("authenticated"):
        return jsonify({"reply": "Unauthorized"}), 403  # GafComment: You had invalid logic here

    user_msg = request.form.get("message", "")
    file = request.files.get("file")

    print("User Message Received:", user_msg)
    print("File Uploaded:", file.filename if file else "No file")

    if file:
        temp_path = os.path.join(tempfile.gettempdir(), file.filename)
        file.save(temp_path)
        with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        collection.add(documents=[content], metadatas=[{"filename": file.filename}], ids=[str(time.time())])

    context = ""
    brave_results = ""
    if user_msg:
        results = collection.query(query_texts=[user_msg], n_results=1)
        if results["documents"] and results["documents"][0]:
            context = results["documents"][0][0][:1000]
        print("ChromaDB Results:", results)

        # --- ENRICH PROMPT WITH BRAVE SEARCH ---
        brave_results = brave_search(user_msg)
        print("Brave Search Results:", brave_results)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_msg}\n\nRelevant Info:\n{context}\n\nWeb Search:\n{brave_results}"}
    ]

    start = time.time()
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=messages,
            temperature=0.7,
            max_tokens=1024
        )
        reply_raw = response.choices[0].message.content
        reply_html = markdown(reply_raw, extensions=['fenced_code', 'tables'])  # GafComment: This was incorrectly placed inside the try block before
    except Exception as e:
        reply_html = f"Error: {e}"

    duration = time.time() - start
    return jsonify({"reply": f"<small>[{duration:.2f}s]</small><br>{reply_html}"})


# --- RUN ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
