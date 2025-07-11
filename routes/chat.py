# routes/chat.py

import time
import logging
import os
import requests
import markdown2

from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)
from config import SYSTEM_PROMPT, drive_service, FOLDER_ID
from rag.drive import load_drive_docs

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("/", methods=["GET", "POST"])
def chat_ui():
    """
    GET  /chat/ → if not authenticated, show password form (index.html);
                    otherwise show main UI (sol.html).
    POST /chat/ → handle password submission.
    """
    # 1) If this is a password POST
    if request.method == "POST" and "password" in request.form:
        pw = request.form["password"]
        if pw == os.getenv("SOL_GPT_PASSWORD"):
            session["authenticated"] = True
            return redirect(url_for("chat.chat_ui"))
        else:
            # bad password → re-render index.html with error message
            return render_template("index.html", error="Incorrect password"), 401

    # 2) If not yet logged in, show login form
    if not session.get("authenticated"):
        return render_template("index.html"), 200

    # 3) Otherwise, serve your chat UI
    return render_template("sol.html"), 200


@chat_bp.route("/api", methods=["POST"])
def chat_api():
    """
    POST /chat/api → your AJAX chat endpoint.
    Expects form-data fields: message, file (optional), show_sources.
    Returns JSON { reply: <HTML string>, duration: <seconds>, html: null }.
    """
    # Must be logged in
    if not session.get("authenticated"):
        return jsonify({"reply": "Not authenticated", "duration": "", "html": None}), 401

    # read sources toggle
    show = request.form.get("show_sources", "true") == "true"
    session["show_sources"] = show

    # optionally load RAG contexts from Drive
    drive_contexts, drive_sources = [], []
    if show and drive_service and FOLDER_ID:
        docs = load_drive_docs(drive_service, FOLDER_ID)
        for chunk, src in docs[:3]:
            drive_contexts.append(chunk)
            drive_sources.append(src)

    duration_str = ""
    structured_html = "⚠️ Sorry, something went wrong."

    try:
        # 1) Grab user message
        user_msg = request.form.get("message", "").strip()

        # 2) Update session history (keep last 20)
        history = session.setdefault("history", [])
        history.append({"role": "user", "content": user_msg})
        session["history"] = history[-20:]

        # 3) Inject Drive snippets, if any
        user_block = user_msg
        if drive_contexts:
            snippets = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(drive_contexts))
            user_block += f"\n\nDrive Snippets:\n{snippets}"

        # 4) Build messages payload
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user",   "content": user_block}]
            + session["history"]
        )

        # 5) Call your LLM
        start = time.time()
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={"model": "llama3-8b-8192", "messages": messages, "temperature": 0.6},
            timeout=30
        )
        resp.raise_for_status()
        reply_md = resp.json()["choices"][0]["message"]["content"]
        duration_str = f"[{time.time() - start:.2f}s]"

        # 6) Markdown → HTML
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks", "tables", "strike", "task_list"]
        )

        # 7) Build sources list
        sources = []
        if show and drive_sources:
            cit = "<h4>Drive Sources</h4><ul>"
            for src in dict.fromkeys(drive_sources):
                cit += f"<li>{src}</li>"
            cit += "</ul>"
            sources.append(cit)

        # 8) Stitch together
        structured_html = reply_html + ( "<hr>" + "".join(sources) if sources else "" )

        # 9) Save assistant reply into history
        session["history"].append({"role": "assistant", "content": reply_md})

    except Exception:
        logging.exception("🔥 Unhandled error in /chat/api:")

    # 10) Return JSON
    return jsonify({
        "reply": structured_html,
        "duration": duration_str,
        "html": None
    }), 200
