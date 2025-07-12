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
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        # parse JSON payload
        ctype = request.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = request.get_json(force=True)
        else:
            return jsonify({
                "error": "Unsupported Media Type",
                "details": f"Expected application/json, got {ctype}"
            }), 415

        # auth guard
        if not session.get("authenticated"):
            return jsonify({
                "reply": "Not authenticated",
                "duration": "",
                "html": None
            }), 401

        # user input
        user_msg = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        # update history
        history = session.get("history", [])
        history.append({"role": "user", "content": user_msg})

        # get model name
        model_name = os.getenv("GROQ_MODEL", "llama3-8b-8192").strip()

        # load RAG docs
        docs_raw = load_drive_docs(drive_service, FOLDER_ID)
        # unify to list
        docs_list = docs_raw[0] if isinstance(docs_raw, tuple) else docs_raw

        # build augmented prompt
        augmented = SYSTEM_PROMPT
        if docs_list:
            snippets = []
            for d in docs_list[:3]:
                if hasattr(d, 'page_content'):
                    snippets.append(d.page_content)
                elif isinstance(d, str):
                    snippets.append(d)
            augmented += "\n\n" + "\n\n".join(snippets)

        # call Groq chat
        chat_completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": augmented}] + history,
            max_tokens=512,
            temperature=0.7
        )

        assistant_msg = chat_completion.choices[0].message.content
        duration = f"[{getattr(chat_completion, 'latency', 0):.2f}s]"

        # persist reply
        history.append({"role": "assistant", "content": assistant_msg})
        session["history"] = history

        # build HTML
        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and getattr(chat_completion, 'sources', None):
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
            "details": last
        }), 500
