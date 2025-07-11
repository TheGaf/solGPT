# routes/chat.py

import logging
import os
import traceback

from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)
from config import SYSTEM_PROMPT, drive_service, FOLDER_ID, client  # make sure `client` is your Groq client

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("/", methods=["GET", "POST"])
def chat_ui():
    # Initialize chat history in session
    if 'history' not in session:
        session['history'] = []

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


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Health check and CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({ "status": "ok" }), 200

    # Real chat POST
    try:
        data = request.get_json(force=True)
        logging.info("Chat payload: %s", data)

        # Authentication guard
        if not session.get("authenticated"):
            return jsonify({ "reply": "Not authenticated", "duration": "", "html": None }), 401

        user_msg = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        # Build your conversation history
        history = session.get("history", [])
        history.append({ "role": "user", "content": user_msg })

        # Call the Groq Llama model
        response = client.predict(
            SYSTEM_PROMPT,
            messages=history,
            model=os.getenv("GROQ_MODEL", "llama-2-7b-chat"),
            max_tokens=512
        )

        assistant_msg = response.generations[0].message or ""
        duration = f"[{response.latency:.2f}s]"

        # Save assistant message into history
        history.append({ "role": "assistant", "content": assistant_msg })
        session["history"] = history  # persist

        # Optionally render HTML for UI
        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and hasattr(response, "sources"):
            # If your RAG call returned `sources`, you can append them:
            sources_html = "<ul>" + "".join(f"<li>{src}</li>" for src in response.sources) + "</ul>"
            reply_html += sources_html

        return jsonify({
            "reply": assistant_msg,
            "html": reply_html,
            "duration": duration
        }), 200

    except Exception:
        # Log the full traceback so you can inspect it in your Render logs
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        # Return a 500 with the error to help diagnose in-browser
        return jsonify({
            "error": "Internal server error",
            "details": traceback.format_exc().splitlines()[-1]
        }), 500
