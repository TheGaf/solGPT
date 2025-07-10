# routes/chat.py

import time
import logging
import os
import requests
import markdown2

from flask import (
    Blueprint, request, jsonify, session,
    current_app, render_template, redirect, url_for
)
from config import SYSTEM_PROMPT, text_collection, drive_service, FOLDER_ID
from rag.drive import load_drive_docs

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.route('', methods=['GET', 'POST'])
def chat_home():
    # ———————————————————————————
    # 1) Unauthenticated GET → login form
    # ———————————————————————————
    if request.method == 'GET' and not session.get('authenticated'):
        return render_template('index.html'), 200

    # ———————————————————————————
    # 2) POST with password → auth check
    # ———————————————————————————
    if request.method == 'POST' and 'password' in request.form:
        pw = request.form.get('password', '')
        if pw == os.getenv("SOL_GPT_PASSWORD"):
            session['authenticated'] = True
            return redirect(url_for('chat.chat_home'))
        else:
            return render_template('index.html', error="Incorrect password"), 401

    # ———————————————————————————
    # 3) Authenticated GET → serve chat UI
    # ———————————————————————————
    if request.method == 'GET':
        return current_app.page_html, 200

    # ———————————————————————————
    # 4) POST → handle a chat message
    # ———————————————————————————
    # read show_sources toggle
    show = request.form.get('show_sources', 'true') == 'true'
    session['show_sources'] = show

    # prepare Drive-RAG if enabled
    drive_contexts, drive_sources = [], []
    if show and drive_service and FOLDER_ID:
        docs = load_drive_docs(drive_service, FOLDER_ID)
        # take first three chunks
        for text_chunk, source_name in docs[:3]:
            drive_contexts.append(text_chunk)
            drive_sources.append(source_name)

    # defaults
    duration_str = ""
    structured_html = "⚠️ Sorry, something went wrong."

    try:
        # guard: must be authenticated
        if not session.get('authenticated'):
            return jsonify({
                'reply': 'Not authenticated',
                'duration': '',
                'html': None
            }), 401

        # get user message
        user_msg = request.form.get('message', '').strip()

        # update session history (last 20)
        history = session.setdefault('history', [])
        history.append({'role': 'user', 'content': user_msg})
        session['history'] = history[-20:]

        # inject drive snippets into user block
        user_block = user_msg
        if drive_contexts:
            snippet_text = "\n\n".join(
                f"[{i+1}] {c}" for i, c in enumerate(drive_contexts)
            )
            user_block = f"{user_msg}\n\nDrive Snippets:\n{snippet_text}"

        # assemble messages array
        messages = (
            [{'role': 'system', 'content': SYSTEM_PROMPT},
             {'role': 'user',   'content': user_block}]
            + session['history']
        )

        # call your LLM endpoint
        start = time.time()
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
        resp.raise_for_status()
        reply_md = resp.json()['choices'][0]['message']['content']
        duration_str = f"[{time.time() - start:.2f}s]"

        # markdown → HTML
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks", "tables", "strike", "task_list"]
        )

        # build a little source list if requested
        sources = []
        if show and drive_sources:
            cit = '<h4>Drive Sources</h4><ul>'
            for src in dict.fromkeys(drive_sources):
                cit += f"<li>{src}</li>"
            cit += "</ul>"
            sources.append(cit)

        # combine reply + optional sources
        structured_html = reply_html
        if sources:
            structured_html += "<hr>" + "".join(sources)

        # append to session history
        session['history'].append({
            'role': 'assistant',
            'content': reply_md
        })

    except Exception:
        logging.exception("🔥 Unhandled error in /chat:")

    # always return JSON 200
    return jsonify({
        'reply': structured_html,
        'duration': duration_str,
        'html': None
    }), 200
