# routes/chat.py

import logging
import os
import traceback

from rag.drive import load_drive_docs
from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)
from markdown2 import markdown  # ← server‐side markdown
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
        # --- parse & auth guard ---
        ctype = request.headers.get("Content-Type", "")
        if not ctype.startswith("application/json"):
            return jsonify({
                "error": "Unsupported Media Type",
                "details": f"Expected application/json, got {ctype}"
            }), 415

        data = request.get_json(force=True)
        if not session.get("authenticated"):
            return jsonify({"reply":"Not authenticated","duration":"","html":None}), 401

        user_msg     = data.get("message","").strip()
        show_sources = bool(data.get("show_sources", False))

        # --- history ---
        history = session["history"]
        history.append({"role":"user","content":user_msg})

        # --- build prompt with Drive RAG ---
        model_name = os.getenv("GROQ_MODEL","llama3-8b-8192").strip()
        raw_docs   = load_drive_docs(drive_service, FOLDER_ID)
        # always get a flat list of strings
        docs_list = []
        for entry in (raw_docs if isinstance(raw_docs,list) else (raw_docs[0] if isinstance(raw_docs,tuple) else [])):
            if hasattr(entry,"page_content"):
                docs_list.append(entry.page_content)
            elif isinstance(entry,str):
                docs_list.append(entry)

        prompt = SYSTEM_PROMPT
        if docs_list:
            prompt += "\n\n" + "\n\n".join(docs_list[:3])

        # --- call Groq chat ---
        chat_c = client.chat.completions.create(
            model=model_name,
            messages=[{"role":"system","content":prompt}] + history,
            max_tokens=512,
            temperature=0.7,
        )

        assistant_msg = chat_c.choices[0].message.content
        duration      = f"[{getattr(chat_c,'latency',0):.2f}s]"

        # persist
        history.append({"role":"assistant","content":assistant_msg})
        session["history"] = history

        # --- Render Markdown → HTML server‐side ---
        html_body = markdown(assistant_msg)
        # optionally append sources list if you got any
        if show_sources and getattr(chat_c, "sources", None):
            srcs = "".join(f"<li>{s}</li>" for s in chat_c.sources)
            html_body += f"<ul class='sources'>{srcs}</ul>"

        return jsonify({
            "reply": assistant_msg,
            "html":  html_body,
            "duration": duration
        }), 200

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({"error":"Internal server error","details":last}), 500
