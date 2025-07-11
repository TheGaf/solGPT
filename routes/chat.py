# routes/chat.py

import logging
import os
import traceback
from datetime import datetime

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
            else:
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


@chat_bp.route("/api", methods=["GET","POST","OPTIONS"])
def chat_api():
    if request.method in ("GET","OPTIONS"):
        return jsonify({"status":"ok"}),200

    try:
        # parse JSON
        data = request.get_json(force=True)

        # auth guard
        if not session.get("authenticated"):
            return jsonify({"reply":"Not authenticated"}),401

        user_msg = data.get("message","").strip()
        show_sources = bool(data.get("show_sources",False))

        history = session.setdefault("history",[])
        history.append({"role":"user","content":user_msg})

        # pick model
        model_name = os.getenv("GROQ_MODEL","").strip() or "llama-2-7b-chat"

        # call Groq
        chat_completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role":"system","content":SYSTEM_PROMPT}] + history,
            max_tokens=512,
            temperature=0.7
        )

        assistant_msg = chat_completion.choices[0].message.content
        duration = "[%.2fs]" % getattr(chat_completion, "latency", 0.0)

        history.append({"role":"assistant","content":assistant_msg})
        session["history"] = history

        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and getattr(chat_completion, "sources",None):
            items = "".join(f"<li>{s}</li>" for s in chat_completion.sources)
            reply_html += f"<ul class='sources'>{items}</ul>"

        return jsonify({"reply":assistant_msg,"html":reply_html,"duration":duration}),200

    except Exception:
        logging.error("Error calling model %r:\n%s", model_name, traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({"error":"Internal server error","details":f"{last} (model={model_name})"}),500
