from flask import Blueprint, request, jsonify, session
import time
import os
import logging
import markdownify
import requests
from config import SYSTEM_PROMPT, text_collection, drive_service, FOLDER_ID
from helpers.web import brave_search, format_brave_html
from helpers.text import split_text
from rag.drive import load_drive_docs
from rag.image import query_image_context
from chromadb.utils import embedding_functions

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('', methods=['GET', 'POST'])
def chat_home():
    # Serve the UI
    if request.method == 'GET':
        from main import page_html
        return page_html, 200

    # Authentication
    if not session.get('authenticated'):
        return jsonify({"error": "Not authenticated"}), 401

    user_msg = request.form.get('message', '').strip()
    lower = user_msg.lower()

    # Toggle source display
    if 'stop showing me sources' in lower:
        session['show_sources'] = False
        return jsonify({'reply': "Understood: I'll hide sources unless you ask.", 'duration': '', 'html': None})
    if 'show sources' in lower:
        session['show_sources'] = True
        return jsonify({'reply': 'Got it: I'll show sources again.', 'duration': '', 'html': None})

    show = session.get('show_sources', True)

    # Append to history
    history = session.setdefault('history', [])
    history.append({'role': 'user', 'content': user_msg})
    session['history'] = history[-20:]

    # RAG contexts (Drive, Image, Web) if enabled
    drive_contexts, drive_sources = [], []
    if drive_service and show:
        try:
            res = text_collection.query(query_texts=[user_msg], n_results=3)
            docs, metas = res['documents'][0], res['metadatas'][0]
            for d, m in zip(docs, metas):
                drive_contexts.append(d)
                drive_sources.append(m.get('source'))
        except Exception as e:
            logging.warning(f"Drive RAG failed: {e}")

    image_context, image_source = '', None
    if show and request.files.get('file'):
        image_context, image_source = query_image_context(request.files['file'])

    brave_html = ''
    if show:
        results = brave_search(user_msg)
        brave_html = format_brave_html(results)

    # Build prompt
    parts = [user_msg]
    if drive_contexts:
        parts.append('Drive Context:\n\n' + '\n\n'.join(f'[{i+1}] {c}' for i, c in enumerate(drive_contexts)))
    if image_context:
        parts.append(f'Image Context from [{image_source}]:\n{image_context}')
    if brave_html:
        parts.append('Web Search Results:')
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + session['history']

    # LLM call
    start = time.time()
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama3-8b-8192",
                "messages": messages,
                "temperature": 0.6,
            },
            timeout=30,
        )
        resp.raise_for_status()
        reply_md = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"LLM call failed: {e}")
        return jsonify({'reply': '⚠️ Error', 'duration': '', 'html': None}), 500
    duration = time.time() - start

    # Save assistant reply
    session['history'] = (session['history'] + [{'role': 'assistant', 'content': reply_md}])[-20:]

    # Convert to HTML
    reply_html = markdownify.markdownify(reply_md, heading_style="ATX")
    sources = []
    if show:
        if drive_sources:
            sources.append('<h4>Drive Sources</h4>' + '<br>'.join(f'[{i+1}] {s}' for i, s in enumerate(drive_sources)))
        if image_source:
            sources.append(f'<h4>Image Source</h4>[{image_source}]')
        if brave_html:
            sources.append(f'<h4>Web Sources</h4>{brave_html}')
    structured_html = reply_html + ('<hr>' + ''.join(sources) if sources else '')

    return jsonify({'reply': structured_html, 'duration': f"[{duration:.2f}s]", 'html': None})
