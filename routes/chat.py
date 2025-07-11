# routes/chat.py

import logging
import os
import traceback

from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("", methods=["GET", "POST"])
@chat_bp.route("/", methods=["GET", "POST"])
def chat_ui():
    try:
        # Initialize chat history in session
        if "history" not in session:
            session["history"] = []

        # Handle login form
        if request.method == "POST" and "password" in request.form:
            if request.form["password"] == os.getenv("SOL_GPT_PASSWORD"):
                session["authenticated"] = True
                return redirect(url_for("chat.chat_ui"))
            else:
                return render_template("index.html", error="Incorrect password"), 401

        # If not authenticated, show login
        if not session.get("authenticated"):
            return render_template("index.html"), 200

        # If authenticated, serve chat UI
        return render_template("sol.html"), 200

    except Exception as err:
        # Log full traceback server-side
        logging.error("🚨 crash in chat_ui:\n%s", traceback.format_exc())
        # Return the error message in the browser so you can see what's missing
        return (
            f"<h1>UI Load Error</h1>"
            f"<pre>{traceback.format_exc()}</pre>",
            500,
        )


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Allow health check and CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        # Parse JSON or form data
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

        # Auth guard
        if not session.get("authenticated"):
            return jsonify({
                "reply": "Not authenticated",
                "duration": "",
                "html": None
            }), 401

        # Echo stub (replace with your Llama/Groq call)
        user_msg = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        reply_html = (
            f"<p><strong>Echo:</strong> {user_msg}</p>"
            f"<p><em>Show sources?</em> {show_sources}</p>"
        )

        return jsonify({
            "reply": user_msg,
            "html": reply_html,
            "duration": "[0.00s]"
        }), 200

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({
            "error": "Internal server error",
            "details": last
        }), 500
