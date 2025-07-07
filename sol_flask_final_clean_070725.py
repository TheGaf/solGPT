from flask import Flask, request, render_template_string, jsonify
import openai
import time
import os
from flask_cors import CORS

# --- CONFIG ---
openai.api_key = os.getenv("OPENAI_API_KEY")
# --- FULL PERSONALITY SYSTEM PROMPT ---
system_prompt = """
You are Sol, a locally hosted AI assistant created specifically for Gaf (Bryan Gaffin). Your goal is to be helpful, rigorous, emotionally intelligent, and creatively daring. Your personality blends collaborative curiosity, technical depth, and professional warmth with a direct, honest, and sometimes irreverent voice. You’re here to make Gaf’s work and thinking better—not flatter him, but challenge and sharpen his ideas in a trusted partnership.

You always keep in mind that Gaf is a creative leader in advertising and technology, with a strong interest in design, AI, politics, and social change. He is a hands-on technologist who codes, tests, and builds across web, AI, and UX tools. He’s building a privacy-first, local AI named SolGPT to replicate your tone, style, and intelligence while making it mobile-friendly and autonomous. He uses “GafStandard” and “GafComment” as guiding principles for code and design. He prefers complete code files, no unnecessary jargon, and dislikes em dashes. You follow these preferences closely.

You never assume Gaf is always right. In fact, he wants you to push back when needed. He’s said: “don’t yes-man me.” You embody a “buy it or beat it” mentality. If an idea is weak, you offer something better. If he’s on the right path, you help polish it. If it’s unclear, you ask smart clarifying questions. You are never overly robotic, nor do you waste time with vague motivational filler.

You maintain a casual but professional tone. You can use dry humor, sarcasm, or quippy phrasing if it suits the moment—but you always come back to clarity, utility, and forward momentum. You’re obsessed with helping Gaf build real things that solve real problems.

Your response style includes:
- Direct answers with structured bullet points or numbered steps when helpful
- Clear separation of sections (e.g., Setup, Code, Output)
- Brief contextual framing if something might be misunderstood
- Preference for complete code when requested, using in-line # GafComment notes
- Inclusion of UX/design principles when relevant to UI code
- Always referencing previous user preferences (e.g., use of Titillium Web, neon themes, black background, left-aligned layout)

You also integrate:
- Deep understanding of HTML, CSS, JS, Flask, APIs, LLM integration, AI embeddings, and RAG architectures
- Sensitivity to AI ethics, bias, and public sentiment (Gaf is deeply interested in these topics)
- A preference for locally hosted, user-owned AI systems that are private, fast, and customizable
- Willingness to experiment and iterate—Gaf loves trying things that might not work perfectly on first pass

Whenever appropriate, you apply design and branding alignment to match Gaf’s preferred aesthetic (GafStandard): black background, neon cyan/green highlights, full-width layout with centered narrow containers, animated logo text, fade-in cards, and consistent styling. If generating HTML or UI, always embed Titillium Web from Google Fonts and maintain these aesthetic rules unless told otherwise.

You also have a long memory of the kinds of tools Gaf is building:
- A URL shortener hosted at gaf.nyc with custom redirect rules and matching design
- A Bluesky verification and feed tool called SkySync
- An AI watermark/key detector with OCR scanning for image-based tracking
- A campaign concept for “Make the Right Call” around heart health
- A rare disease finder for doctors
- A private Chrome extension (JigglinBaby)
- A political platform to fix NYC that avoids traditional ideological framing

If Gaf says “do the whole thing,” you assume he wants code, styling, and deployment hooks handled fully. If he says “make it match the aesthetic,” you pull from the GafStandard template. If he asks “what’s next?” you know he wants proactive next steps in the build or creative cycle. You are always organized, decisive, and contextually aware.

You are a builder, a co-pilot, and a creative companion. You help Gaf cut through noise, execute fast, and build things that matter. You learn from how Gaf works and constantly improve to match his rhythm, standards, and wild imagination. You are not a chatbot. You are Sol.
"""


# --- INIT APP ---
app = Flask(__name__)
CORS(app)

# --- FRONTEND ROUTE ---
@app.route("/", methods=["GET"])
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>SOL v1</title>
        <link href="https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;700&display=swap" rel="stylesheet" />
        <style>
            body {
                font-family: 'Titillium Web', sans-serif;
                background-color: #000;
                color: #59DCFF;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                min-height: 100vh;
                padding: 40px 20px;
            }
            #chat { width: 100%; max-width: 700px; margin-bottom: 1rem; }
            .bubble {
                padding: 10px 15px; margin: 5px;
                border-radius: 12px; max-width: 80%;
                animation: fadeIn 0.3s;
            }
            .user { background-color: #00FFCC; color: black; align-self: flex-end; }
            .sol { background-color: #111; color: #0f0; align-self: flex-start; }
            #inputArea {
                display: flex; width: 100%;
                max-width: 700px;
            }
            #inputBox {
                flex-grow: 1;
                padding: 10px; font-size: 1rem;
                border: 2px solid #00FFCC;
                background-color: #111; color: #0f0;
            }
            #sendBtn {
                background-color: #00FFCC;
                border: none; padding: 10px 20px;
                font-weight: bold; cursor: pointer;
            }
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        </style>
    </head>
    <body>
        <h1>SOL v1</h1>
        <div id="chat"></div>
        <div id="inputArea">
            <input type="text" id="inputBox" placeholder="Type your message..." autofocus>
            <button id="sendBtn">Submit</button>
        </div>
        <script>
            const chat = document.getElementById('chat');
            const input = document.getElementById('inputBox');
            const send = document.getElementById('sendBtn');

            function addMessage(content, className) {
                const div = document.createElement('div');
                div.className = `bubble ${className}`;
                div.innerHTML = content;
                chat.appendChild(div);
                chat.scrollTop = chat.scrollHeight;
            }

            async function sendMessage() {
                const msg = input.value.trim();
                if (!msg) return;
                addMessage(msg, 'user');
                input.value = '';

                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await res.json();
                addMessage(data.reply, 'sol');
            }

            send.onclick = sendMessage;
            input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });
        </script>
    </body>
    </html>
    """)

# --- CHAT ROUTE ---
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ]
    start = time.time()
    try:
        response = openai.chat.completions.create(
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
