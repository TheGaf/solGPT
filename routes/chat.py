# routes/chat.py

import logging
import os
import traceback

from rag.drive import load_drive_docs
from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)
from markdown2 import markdown
from config import SYSTEM_PROMPT, client, drive_service, FOLDER_ID

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("", methods=["GET", "POST"])
@chat_bp.route("/", methods=["GET", "POST"])
def chat_ui():
    try:
        if "history" not in session:
            session["history"] = []

        if request.method == "POST" and "password" in request.form:
            if request.form["password"] == os.getenv("SOL_GPT_PASSWORD"):
                session["authenticated"] = True
                return redirect(url_for("chat.chat_ui"))
            return render_template("index.html", error="Incorrect password"), 401

        if not session.get("authenticated"):
            return render_template("index.html"), 200

        return render_template("sol.html"), 200

    except Exception:
        logging.error("🚨 crash in chat_ui:\n%s", traceback.format_exc())
        return (
            "<h1>UI Load Error</h1>"
            f"<pre>{traceback.format_exc()}</pre>",
            500,
        )


@chat_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("chat.chat_ui"))


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    # Health‐check and CORS preflight
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        # Determine content type
        ctype = request.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = request.get_json(force=True)
            user_msg = data.get("message", "").strip()
            show_sources = bool(data.get("show_sources", False))
            file = None
        elif "multipart/form-data" in ctype:
            user_msg = request.form.get("message", "").strip()
            show_sources = request.form.get("show_sources", "false").lower() == "true"
            file = request.files.get("file")
        else:
            return jsonify({
                "error": "Unsupported Media Type",
                "details": f"Expected JSON or multipart/form-data, got {ctype}"
            }), 415

        # Authentication guard
        if not session.get("authenticated"):
            return jsonify({"reply":"Not authenticated","duration":"","html":None}), 401

        # Handle file upload
        if file:
            # Upload to Google Drive
            drive_file = drive_service.files().create(
                body={"name": file.filename, "parents": [FOLDER_ID]},
                media_body=file,
                fields="id"
            ).execute()
            file_id = drive_file["id"]
            # Make it publicly readable
            drive_service.permissions().create(
                fileId=file_id,
                body={"role":"reader","type":"anyone"}
            ).execute()
            view_url = f"https://drive.google.com/file/d/{file_id}/view"
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download"

            html = (
                f"<p>Uploaded <strong>{file.filename}</strong></p>"
                f"<a href=\"{view_url}\" target=\"_blank\">"
                f"<img src=\"{download_url}\" "
                "style=\"max-width:200px;border-radius:6px;margin:6px 0;\"/>"
                "</a>"
            )
            return jsonify({"reply": file.filename, "html": html, "duration": ""}), 200

        # Text message path: update & cap history
        history = session.get("history", [])
        history.append({"role": "user", "content": user_msg})
        history = history[-50:]
        session["history"] = history

        # Determine model name
        model_name = os.getenv("GROQ_MODEL", "llama3-8b-8192").strip()

        # RAG: load Drive docs and flatten
        raw_docs = load_drive_docs(drive_service, FOLDER_ID)
        docs_list = raw_docs[0] if isinstance(raw_docs, tuple) else raw_docs
        snippets = []
        for d in docs_list[:3]:
            if hasattr(d, "page_content"):
                snippets.append(d.page_content)
            elif isinstance(d, str):
                snippets.append(d)
        prompt = SYSTEM_PROMPT
        if snippets:
            prompt += "\n\n" + "\n\n".join(snippets)

        # Call Groq chat completion
        chat_c = client.chat.completions.create(
            model=model_name,
            messages=[{"role":"system","content":prompt}] + history,
            max_tokens=512,
            temperature=0.7
        )

        assistant_msg = chat_c.choices[0].message.content
        duration = f"[{getattr(chat_c, 'latency', 0):.2f}s]"

        # Persist assistant reply
        history.append({"role":"assistant","content":assistant_msg})
        session["history"] = history

        # Server‐side Markdown → HTML
        html_body = markdown(assistant_msg)
        if show_sources and getattr(chat_c, "sources", None):
            srcs = "".join(f"<li>{s}</li>" for s in chat_c.sources)
            html_body += f"<ul class='sources'>{srcs}</ul>"

        return jsonify({"reply": assistant_msg, "html": html_body, "duration": duration}), 200

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({"error":"Internal server error","details":last}), 500
