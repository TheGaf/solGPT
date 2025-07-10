# routes/chat.py

from flask import Blueprint, request, jsonify, session
import time, logging, os
import markdownify, requests
from config import SYSTEM_PROMPT, text_collection
# … your other imports …

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('', methods=['GET','POST'])
def chat_home():
    # Quick guard so GET still returns your UI
    if request.method == 'GET':
        from main import page_html
        return page_html, 200

    # Wrap everything in one try/except
    try:
        # — your entire POST logic goes here —
        user_msg = request.form.get('message','').strip()
        # … rest of your handler as before …
        # At the end:
        return jsonify({
            'reply': structured_html,
            'duration': f"[{duration:.2f}s]",
            'html': None
        }), 200

    except Exception as e:
        # This will show the full Python traceback in your Render logs
        logging.exception("🔥 Unhandled error in /chat:")
        # This returns a harmless JSON so your UI doesn’t see a 502
        return jsonify({
            'reply': "⚠️ Sorry, something unexpected happened on the server.",
            'duration': '',
            'html': None
        }), 200
