from flask import Blueprint, request, jsonify, session
import time
import os

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('', methods=['GET', 'POST'])
def chat_home():
    if request.method == 'GET':
        from main import page_html
        return page_html, 200
    if not session.get('authenticated'):
        return jsonify({"error": "Not authenticated"}), 401
    user_msg = request.form.get('message', '')
    # Stub reply
    return jsonify({"reply": f"Echo: {user_msg}"}), 200
