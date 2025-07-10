# routes/chat.py

import time
import logging
import os
import requests
import markdown2

from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for, current_app
)
from config import SYSTEM_PROMPT, text_collection, drive_service, FOLDER_ID
from rag.drive import load_drive_docs

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')
@chat_bp.route('/', methods=['GET', 'POST'])
def chat_home():
    # 1) GET + not authenticated → show login form
    if request.method == 'GET' and not session.get('authenticated'):
        return render_template('index.html'), 200

    # 2) POST for login (password field present)
    if request.method == 'POST' and 'password' in request.form:
        pw = request.form.get('password', '')
        if pw == os.getenv("SOL_GPT_PASSWORD"):
            session['authenticated'] = True
            return redirect(url_for('chat.chat_home'))
        else:
            return render_template('index.html', error="Incorrect password"), 401

    # 3) GET + authenticated → show chat UI
    if request.method == 'GET':
        return render_template('sol.html'), 200

    # From here on, it's a POST to send/receive chat messages.

    # 4) Store the "show sources" toggle
    show = request.form.get('show_sources', 'true') == 'true'
    session['show_sources'] = show

    # 5) Drive RAG contexts
    drive_contexts, drive_sources = [], []
    if show and drive_service and FOLDER_ID:
        docs = load_drive_docs(drive_service, FOLDER_ID)
        for text_chunk, source_name in docs[:3]:
            drive_contexts.append(text_chunk)
            drive_sources.append(source_name)

    # Defaults
    structured_html = "⚠️ Sorry, something went wrong."
    duration_str    = ""

    try:
        # 6) Auth guard for chat POST
        if not session.get('authenticated'):
            return jsonify({'reply': 'Not authenticated', 'duration': '', 'html': None}), 401

        # 7) Gather user message
        user_msg = request.form.get('message', '').strip()

        # 8) Update session history
        history = session.setdefault('history', [])
        history.append({'role': 'user', 'content': user_msg})
        session['history'] = history[-20:]

        # 9) Build prompt with Drive snippets if any
        user_block = user_msg
        if drive_contexts:
            snippet = "\n\n".join(f"[{i+1}] {c}"
                                 for i, c in enumerate(drive_contexts))
            user_block = f"{user_msg}\n\nDrive Snippets:\n{snippet}"

        # 10) Assemble messages
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': user_block}
        ] + session['history']

        # 11) Call Groq API
        start = time.time()
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama3-8b-8192",
                "messages":    messages,
                "temperature": 0.6
            },
            timeout=30
        )
        resp.raise_for_status()
        reply_md     = resp.json()['choices'][0]['message']['content']
        duration_str = f"[{time.time() - start:.2f}s]"

        # 12) Markdown → HTML
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks", "tables", "strike", "task_list"]
        )

        # 13) Build sources block
        sources = []
        if show and drive_sources:
            block = '<h4>Drive Sources</h4><ul>'
            for src in dict.fromkeys(drive_sources):
                block += f"<li>{src}</li>"
            block += "</ul>"
            sources.append(block)

        # 14) Combine
        structured_html = reply_html
        if sources:
            structured_html += "<hr>" + "".join(sources)

        # 15) Save assistant reply
        session['history'].append({'role': 'assistant', 'content': reply_md})

    except Exception:
        logging.exception("🔥 Unhandled error in /chat:")

    # 16) Return JSON response
    return jsonify({
        'reply': structured_html,
        'duration': duration_str,
        'html': None
    }), 200
