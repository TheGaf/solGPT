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
from config import SYSTEM_PROMPT, drive_service, FOLDER_ID
from rag.drive import load_drive_docs

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.route("", methods=['GET', 'POST'])
def chat_home():
    # 1) Unauthenticated GET → login form
    if request.method == 'GET' and not session.get('authenticated'):
        return render_template('index.html'), 200

    # 2) POST with password → auth check
    if request.method == 'POST' and 'password' in request.form:
        pw = request.form.get('password', '')
        if pw == os.getenv("SOL_GPT_PASSWORD"):
            session['authenticated'] = True
            return redirect(url_for('chat.chat_home'))
        else:
            return render_template('index.html', error="Incorrect password"), 401

    # 3) Authenticated GET → render chat UI
    if request.method == 'GET':
        return render_template('sol.html'), 200

    # 4) Authenticated POST → handle chat message
    show = request.form.get('show_sources', 'true') == 'true'
    session['show_sources'] = show

    # Prepare Drive-RAG contexts
    drive_contexts, drive_sources = [], []
    if show and drive_service and FOLDER_ID:
        docs = load_drive_docs(drive_service, FOLDER_ID)
        for chunk, src in docs[:3]:
            drive_contexts.append(chunk)
            drive_sources.append(src)

    duration_str = ""
    structured_html = "⚠️ Sorry, something went wrong."

    try:
        # Auth guard
        if not session.get('authenticated'):
            return jsonify({'reply': 'Not authenticated', 'duration': '', 'html': None}), 401

        # Get user message
        user_msg = request.form.get('message', '').strip()

        # Update session history
        history = session.setdefault('history', [])
        history.append({'role': 'user', 'content': user_msg})
        session['history'] = history[-20:]

        # Inject Drive snippets
        user_block = user_msg
        if drive_contexts:
            snippets = "\n\n".join(f"[{i+1}] {c}"
                                   for i, c in enumerate(drive_contexts))
            user_block += f"\n\nDrive Snippets:\n{snippets}"

        # Assemble messages
        messages = (
            [{'role': 'system', 'content': SYSTEM_PROMPT},
             {'role': 'user',   'content': user_block}]
            + session['history']
        )

        # ——————————————
        # Call Groq with retry/backoff on 429
        # ——————————————
        start = time.time()
        reply_md = None
        for attempt in range(3):
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": messages,
                    "temperature": 0.6
                },
                timeout=30
            )
            if resp.status_code == 429:
                # rate limited → exponential backoff
                time.sleep(2 ** attempt)
                continue

            resp.raise_for_status()
            reply_md = resp.json()['choices'][0]['message']['content']
            break

        if reply_md is None:
            # still throttled after retries
            structured_html = "⚠️ Service is busy, please try again in a moment."
            session['history'].append({'role':'assistant','content':structured_html})
            return jsonify({'reply': structured_html, 'duration': "", 'html': None}), 200

        duration_str = f"[{time.time() - start:.2f}s]"

        # Markdown → HTML
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks", "tables", "strike", "task_list"]
        )

        # Build sources list
        sources = []
        if show and drive_sources:
            html = '<h4>Drive Sources</h4><ul>'
            for src in dict.fromkeys(drive_sources):
                html += f"<li>{src}</li>"
            html += "</ul>"
            sources.append(html)

        # Combine reply + sources
        structured_html = reply_html
        if sources:
            structured_html += "<hr>" + "".join(sources)

        # Save assistant reply
        session['history'].append({'role':'assistant', 'content': reply_md})

    except Exception:
        logging.exception("🔥 Unhandled error in /chat:")

    # Always return JSON 200
    return jsonify({'reply': structured_html, 'duration': duration_str, 'html': None}), 200
