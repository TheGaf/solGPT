# routes/chat.py

import time
import logging
import os
import requests
import markdown2

from flask import (
    Blueprint,
    request,
    jsonify,
    session,
    current_app,
    render_template,
    redirect,
    url_for
)
from config import SYSTEM_PROMPT, text_collection, drive_service, FOLDER_ID
from rag.drive import load_drive_docs

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('', methods=['GET', 'POST'])
def chat_home():
    try:
        # ——————————————————————————————————————————————
        # 1) GET & not authenticated → show login form
        # ——————————————————————————————————————————————
        if request.method == 'GET' and not session.get('authenticated'):
            return render_template('index.html'), 200

        # ——————————————————————————————————————————————
        # 2) POST & login form submitted → validate and redirect
        # ——————————————————————————————————————————————
        if request.method == 'POST' and 'password' in request.form:
            pw = request.form['password']
            if pw == os.getenv("SOL_GPT_PASSWORD"):
                session['authenticated'] = True
                return redirect(url_for('chat.chat_home'))
            else:
                return render_template(
                    'index.html', error="Incorrect password"
                ), 401

        # ——————————————————————————————————————————————
        # 3) GET & authenticated → serve the pre-fetched UI
        # ——————————————————————————————————————————————
        if request.method == 'GET':
            return current_app.page_html, 200

        # ——————————————————————————————————————————————
        # 4) POST & actual chat message → process chat
        # ——————————————————————————————————————————————
        #   4.1) store show_sources toggle
        show = request.form.get('show_sources', 'true') == 'true'
        session['show_sources'] = show

        #   4.2) load Drive contexts (always returns list)
        drive_contexts, drive_sources = [], []
        if show and drive_service and FOLDER_ID:
            docs = load_drive_docs(drive_service, FOLDER_ID) or []
            for chunk, src in docs[:3]:
                drive_contexts.append(chunk)
                drive_sources.append(src)

        #   4.3) build defaults
        duration_str    = ""
        structured_html = "⚠️ Sorry, something went wrong."

        #   4.4) POST auth guard
        if not session.get('authenticated'):
            return jsonify(reply="Not authenticated", duration="", html=None), 401

        #   4.5) gather user message
        user_msg = request.form.get('message', '').strip()
        history  = session.setdefault('history', [])
        history.append({'role': 'user', 'content': user_msg})
        session['history'] = history[-20:]

        #   4.6) inject Drive snippets into the prompt
        prompt_block = user_msg
        if drive_contexts:
            bits = "\n\n".join(f"[{i+1}] {c}"
                               for i, c in enumerate(drive_contexts))
            prompt_block = f"{user_msg}\n\nDrive Snippets:\n{bits}"

        #   4.7) assemble messages for LLM
        messages = (
            [{'role': 'system', 'content': SYSTEM_PROMPT},
             {'role': 'user',   'content': prompt_block}]
            + session['history']
        )

        #   4.8) call Groq
        start = time.time()
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": messages,
                "temperature": 0.6
            },
            timeout=30
        )
        resp.raise_for_status()
        reply_md    = resp.json()['choices'][0]['message']['content']
        duration_str = f"[{time.time() - start:.2f}s]"

        #   4.9) convert markdown → HTML
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks", "tables", "strike", "task_list"]
        )

        #   4.10) build sources HTML
        sources_html = ""
        if show and drive_sources:
            items = "".join(f"<li>{src}</li>"
                            for src in dict.fromkeys(drive_sources))
            sources_html = f"<h4>Drive Sources</h4><ul>{items}</ul>"

        structured_html = reply_html
        if sources_html:
            structured_html += "<hr>" + sources_html

        #   4.11) save assistant reply to history
        session['history'].append({'role': 'assistant',
                                   'content': reply_md})

        #   4.12) return JSON payload
        return jsonify({
            'reply': structured_html,
            'duration': duration_str,
            'html': None
        }), 200

    except Exception:
        logging.exception("🔥 chat_home failed")
        # on any error, return a simple HTML page (avoids 502)
        return (
            "<h1>Server Error</h1>"
            "<p>Something went wrong. Check logs.</p>",
            500
        )
