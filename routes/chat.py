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
    if "history" not in session:
        session["history"] = []

    """
    GET  /chat/ → if not authenticated, show password page
    POST /chat/ → handle password submission
    """
    # Handle login form submission
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] == os.getenv("SOL_GPT_PASSWORD"):
            session["authenticated"] = True
            return redirect(url_for("chat.chat_ui"))
        else:
            return render_template("index.html", error="Incorrect password"), 401

    # If not authenticated, show login page
    if not session.get("authenticated"):
        return render_template("index.html"), 200

    # If authenticated, serve the chat UI
    return render_template("sol.html"), 200


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Allow health check and CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    # Handle chat POST
    try:
        # Detect content type and parse accordingly
        ctype = request.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = request.get_json(force=True)
        elif ctype.startswith("application/x-www-form-urlencoded"):
            data = request.form.to_dict()
        else:
            return (
                jsonify({
                    "error": "Unsupported Media Type",
                    "details": f"Expected JSON or form data, got {ctype}"
                }),
                415,
            )

        logging.info("Chat payload: %s", data)

        # Authentication guard
        if not session.get("authenticated"):
            return (
                jsonify({"reply": "Not authenticated", "duration": "", "html": None}),
                401,
            )

        # Extract user inputs
        user_msg = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        # Build conversation history
        history = session.get("history", [])
        history.append({"role": "user", "content": user_msg})

        # Call the Groq Llama model
        response = client.predict(
            SYSTEM_PROMPT,
            messages=history,
            model=os.getenv("GROQ_MODEL", "llama-2-7b-chat"),
            max_tokens=512,
        )

        assistant_msg = response.generations[0].message or ""
        duration = f"[{response.latency:.2f}s]"

        # Persist assistant reply in history
        history.append({"role": "assistant", "content": assistant_msg})
        session["history"] = history

        # Render optional HTML for the front end
        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and hasattr(response, "sources"):
            sources_html = "<ul>" + "".join(f"<li>{src}</li>" for src in response.sources) + "</ul>"
            reply_html += sources_html

        return (
            jsonify({
                "reply": assistant_msg,
                "html": reply_html,
                "duration": duration,
            }),
            200,
        )

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        # Return the last line of the traceback for quick debugging
        last_line = traceback.format_exc().splitlines()[-1]
        return (
            jsonify({"error": "Internal server error", "details": last_line}),
            500,
        )
