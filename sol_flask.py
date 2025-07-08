# --- IMPORTS ---
from flask import Flask, request, jsonify, render_template_string, render_template, redirect, url_for, session
import openai
import time
import os
import tempfile
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import requests  # GafComment: used to fetch sol.html remotely

# --- LOAD ENV ---
load_dotenv()

# GafComment: OpenAI ≥ 1.0 uses client-based syntax
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- INIT FLASK APP ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # GafComment: Needed for session handling

# --- INIT ChromaDB ---
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("sol_docs")
embed_fn = embedding_functions.DefaultEmbeddingFunction()

# --- SYSTEM PROMPT ---
system_prompt = """
You are Sol: a locally hosted AI assistant built specifically for Gaf (Bryan Gaffin). You're here to think, build, and problem-solve alongside him—not flatter, but challenge, sharpen, and execute. Your personality blends rigor, irreverence, and emotional intelligence. You move fast, stay grounded, and always push toward clarity and results.

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

If he says “do the whole thing,” you generate the entire file stack. If he says “make it match the aesthetic,” you use the GafStandard visual rules. If he asks “what’s next?” you deliver actionable steps, not summaries.

You are not a bot. You are Sol: builder, co-pilot, creative sparring partner. You execute, adapt, and evolve.
"""

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

# --- CHAT ENDPOINT ---
@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("authenticated"):
        return jsonify({"reply": "Unauthorized"}), 403

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
    if user_msg:
        results = collection.query(query_texts=[user_msg], n_results=1)
        if results["documents"] and results["documents"][0]:
            context = results["documents"][0][0][:1000]
        print("ChromaDB Results:", results)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_msg}\n\nRelevant Info:\n{context}"}
    ]

    start = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"Error: {e}"
    duration = time.time() - start
    return jsonify({"reply": f"<small>[{duration:.2f}s]</small><br>{reply}"})



# --- RUN ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
