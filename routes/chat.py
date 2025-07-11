# routes/chat.py

import logging
import os
from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("/", methods=["GET", "POST"])
def chat_ui():
    # Initialize chat history in session
    if 'history' not in session:
        session['history'] = []

    """
    GET  /chat → if not authenticated, show password page; otherwise serve sol.html
    POST /chat → handle password form
    """
    # Handle login form
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] == os.getenv("SOL_GPT_PASSWORD"):
            session["authenticated"] = True
            return redirect(url_for("chat.chat_ui"))
        else:
            return render_template("index.html", error="Incorrect password"), 401

    # Not authenticated → show login
    if not session.get("authenticated"):
        return render_template("index.html"), 200

    # Authenticated → serve chat UI
    return render_template("sol.html"), 200


@chat_bp.route("/api", methods=["POST"])
def chat_api():
    """
    POST /chat/api
    A stub implementation that simply echoes back the "message" field.
    """
    # Guard: must be authenticated
    if not session.get("authenticated"):
        return jsonify({"reply": "Not authenticated", "duration": "", "html": None}), 401

    # Grab message & toggle
    user_msg = request.form.get("message", "")
    show_sources = request.form.get("show_sources", "true")
    session["show_sources"] = (show_sources == "true")

    # Build a simple HTML reply
    reply_html = (
        f"<p><strong>Echo:</strong> {user_msg!s}</p>"
        f"<p><em>Show sources?</em> {show_sources}</p>"
    )

    # Return JSON
    return jsonify({
        "reply": reply_html,
        "duration": "[0.00s]",
        "html": None
    }), 200
