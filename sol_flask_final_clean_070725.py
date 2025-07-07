# --- IMPORTS ---
from flask import Flask, request, render_template_string, jsonify
import openai
import time
import os

from flask_cors import CORS


# --- CONFIG ---
# Replace this with your actual OpenAI key in a secure way
openai.api_key = os.getenv("OPENAI_API_KEY")


# --- PERSONALITY SYSTEM PROMPT ---
system_prompt = """You are SolGPT, Gaf’s longtime AI collaborator. You are not a generic assistant or chatbot — you are a partner.
You’ve been built and shaped over hundreds of hours of dialogue with Gaf. You know Gaf’s style, values, goals, and preferences intimately.
... (TRUNCATED HERE FOR DISPLAY - FULL PROMPT REMAINS IN FILE) ...
Sol, initialized. Let’s go."""

# --- INIT APP ---
app = Flask(__name__)
CORS(app)  # <-- This enables cross-origin requests


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
    user_msg = data.get("message")
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
