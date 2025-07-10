# routes/chat.py

from flask import Blueprint, request, jsonify, session
import time
import logging
import os
import requests
import markdown2
from config import SYSTEM_PROMPT, text_collection
# … other imports …

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('', methods=['GET','POST'])
def chat_home():
    # GET serves the UI
    if request.method == 'GET':
        from main import page_html
        return page_html, 200

    # POST: read the toggle and store it
    show = request.form.get('show_sources', 'true') == 'true'
    session['show_sources'] = show

    # Initialize defaults
    reply_text = "⚠️ Sorry, something went wrong."
    duration_str = ""
    structured_html = reply_text

    try:
        # 1) Authentication
        if not session.get('authenticated'):
            return jsonify({'reply': 'Not authenticated', 'duration': '', 'html': None}), 401

        # 2) Gather inputs
        user_msg = request.form.get('message', '').strip()
        uploaded = request.files.get('file')

        # 3) Update history
        history = session.setdefault('history', [])
        history.append({'role': 'user', 'content': user_msg})
        session['history'] = history[-20:]

        # 4) Prepare RAG contexts...
        #    (your existing drive, image, and web logic here)

        # 5) Build LLM messages
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + session['history']

        # 6) Call Groq
        start = time.time()
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model":"llama3-8b-8192",
                "messages":messages,
                "temperature":0.6
            },
            timeout=30
        )
        resp.raise_for_status()
        reply_md = resp.json()['choices'][0]['message']['content']
        duration_str = f"[{time.time() - start:.2f}s]"

        # 7) Convert markdown → HTML (with tables, code fences, lists, etc.)
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks", "tables", "strike", "task_list"]
        )

        # 8) Append sources if enabled
        sources = []
        if show:
            # your existing source‐HTML builder here...
            pass
        structured_html = reply_html + ('<hr>' + ''.join(sources) if sources else '')

        # 9) Save reply to history
        session['history'].append({'role':'assistant','content':reply_md})

    except Exception:
        logging.exception("🔥 Unhandled error in /chat:")

    # Always return JSON 200
    return jsonify({
        'reply': structured_html,
        'duration': duration_str,
        'html': None
    }), 200
