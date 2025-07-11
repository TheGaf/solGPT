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
    GET  /chat/ → if not authenticated, show password page; otherwise serve sol.html
    POST /chat/ → handle password form submission
    """
    # Handle login form POST
    if request.method == "POST" and "password" in request.form:
        logging.info("Password attempt for SOL GPT")
        if request.form["password"] == os.getenv("SOL_GPT_PASSWORD"):
            session["authenticated"] = True
            return redirect(url_for("chat.chat_ui"))
        else:
            return render_template("index.html", error="Incorrect password"), 401

    # Not authenticated → show login page
    if not session.get("authenticated"):
        return render_template("index.html"), 200

    # Authenticated → serve the main chat UI
    return render_template("sol.html"), 200


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Health check or CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({ "status": "ok" }), 200

    # Real chat POST
    logging.info("Incoming chat payload: %s", request.get_json())

    # Authentication guard
    if not session.get("authenticated"):
        return jsonify({
            "reply": "Not authenticated",
            "duration": "",
            "html": None
        }), 401

    # Extract inputs
    # If your front end sends JSON:
    data = request.get_json() or {}
    user_msg = data.get("message", "")
    show_sources = data.get("show_sources", True)

    # Persist show-sources preference
    session["show_sources"] = bool(show_sources)

    # TODO: Replace this stub with your real Llama/Groq chat logic
    # For now we simply echo back
    reply_html = (
        f"<p><strong>Echo:</strong> {user_msg}</p>"
        f"<p><em>Show sources?</em> {show_sources}</p>"
    )

    return jsonify({
        "reply": reply_html,
        "duration": "[0.00s]",
        "html": None
    }), 200
