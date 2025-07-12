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
            500,
        )


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Health-check and CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        # Determine content type and extract inputs
        ctype = request.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = request.get_json(force=True)
            user_msg = data.get("message", "").strip()
            show_sources = bool(data.get("show_sources", False))
        else:
            # multipart/form-data: handle file upload
            user_msg = request.form.get("message", "").strip()
            show_sources = request.form.get("show_sources", "false") == "true"
            uploaded = request.files.get("file")
            if uploaded:
                # upload to Google Drive and get URL
                drive_file = drive_service.files().create(
                    body={"name": uploaded.filename, "parents": [FOLDER_ID]},
                    media_body=uploaded,
                    fields="id"
                ).execute()
                file_url = f"https://drive.google.com/uc?id={drive_file['id']}"
                # prefix image link to user message
                user_msg = f"[Image: {file_url}]\n\n{user_msg}"

        # Auth guard
        if not session.get("authenticated"):
            return jsonify({
                "reply": "Not authenticated",
                "duration": "",
                "html": None
            }), 401

        # Update conversation history
        history = session.get("history", [])
        history.append({"role": "user", "content": user_msg})

        # Determine model
        model_name = os.getenv("GROQ_MODEL", "").strip() or "llama3-8b-8192"

        # RAG: load Drive docs safely
        docs_result = load_drive_docs(drive_service, FOLDER_ID)
        docs_list = docs_result[0] if isinstance(docs_result, tuple) else docs_result

        # Build augmented prompt
        augmented_prompt = SYSTEM_PROMPT
        if docs_list:
            snippets = "\n\n".join(doc.page_content for doc in docs_list[:3])
            augmented_prompt += "\n\n" + snippets

        # Call Groq chat completion
        chat_completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": augmented_prompt}] + history,
            max_tokens=512,
            temperature=0.7
        )

        assistant_msg = chat_completion.choices[0].message.content
        duration = f"[{getattr(chat_completion, 'latency', 0):.2f}s]"

        # Persist reply
        history.append({"role": "assistant", "content": assistant_msg})
        session["history"] = history

        # Build HTML
        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and getattr(chat_completion, "sources", None):
            items = "".join(f"<li>{src}</li>" for src in chat_completion.sources)
            reply_html += f"<ul class='sources'>{items}</ul>"

        return jsonify({
            "reply": assistant_msg,
            "html": reply_html,
            "duration": duration
        }), 200

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({
            "error": "Internal server error",
            "details": f"{last} (model={model_name})"
        }), 500
