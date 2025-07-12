# routes/chat.py

import logging
import os
import traceback

from rag.drive import load_drive_docs
from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)
from config import SYSTEM_PROMPT, client, drive_service, FOLDER_ID

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("", methods=["GET", "POST"])
@chat_bp.route("/", methods=["GET", "POST"])
def chat_ui():
    try:
        # Initialize session history
        if "history" not in session:
            session["history"] = []

        # Handle login form
        if request.method == "POST" and "password" in request.form:
            if request.form["password"] == os.getenv("SOL_GPT_PASSWORD"):
                session["authenticated"] = True
                return redirect(url_for("chat.chat_ui"))
            return render_template("index.html", error="Incorrect password"), 401

        # If not authenticated, show login
        if not session.get("authenticated"):
            return render_template("index.html"), 200

        # Authenticated → show chat UI
        return render_template("sol.html"), 200

    except Exception:
        logging.error("🚨 crash in chat_ui:\n%s", traceback.format_exc())
        return (
            "<h1>UI Load Error</h1>"
            f"<pre>{traceback.format_exc()}</pre>",
            500
        )


@chat_bp.route("/logout")
def logout():
    # Clear everything
    session.clear()
    # Render the login page in one shot, avoiding a double‐hop redirect
    try:
        return render_template("index.html"), 200
    except Exception:
        # If for some reason index.html blows up, show a plain fallback
        logging.error("🚨 crash in logout render:\n%s", traceback.format_exc())
        return (
            "<h1>Logged out</h1>"
            "<p>Please <a href='/chat/'>click here</a> to log in again.</p>",
            200
        )


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Health‐check and CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        # Parse JSON payload
        ctype = request.headers.get("Content-Type", "")
        if not ctype.startswith("application/json"):
            return jsonify({
                "error": "Unsupported Media Type",
                "details": f"Expected application/json, got {ctype}"
            }), 415
        data = request.get_json(force=True)

        # Authentication guard
        if not session.get("authenticated"):
            return jsonify({
                "reply": "Not authenticated",
                "duration": "",
                "html": None
            }), 401

        # Extract inputs
        user_msg     = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        # Update conversation history
        history = session.get("history", [])
        history.append({"role": "user", "content": user_msg})

        # Determine model name
        model_name = os.getenv("GROQ_MODEL", "").strip() or "llama3-8b-8192"

        # — RAG STEP: load top 3 Drive docs for context
        docs = load_drive_docs(drive_service, FOLDER_ID)
        augmented_prompt = SYSTEM_PROMPT + "\n\n" + "\n\n".join(
            doc.page_content for doc in docs[:3]
        )

        # Call the Groq chat completion endpoint
        chat_completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": augmented_prompt}] + history,
            max_tokens=512,
            temperature=0.7
        )

        # Extract reply & (optional) latency
        assistant_msg = chat_completion.choices[0].message.content
        duration      = f"[{getattr(chat_completion, 'latency', 0):.2f}s]"

        # Persist assistant reply
        history.append({"role": "assistant", "content": assistant_msg})
        session["history"] = history

        # Build HTML for UI
        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and getattr(chat_completion, "sources", None):
            items = "".join(f"<li>{src}</li>" for src in chat_completion.sources)
            reply_html += f"<ul class='sources'>{items}</ul>"

        return jsonify({
            "reply": assistant_msg,
            "html":  reply_html,
            "duration": duration
        }), 200

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({
            "error": "Internal server error",
            "details": f"{last} (model={model_name})"
        }), 500
