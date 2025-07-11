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


@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        # parse JSON
        ctype = request.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = request.get_json(force=True)
        else:
            return jsonify({
                "error": "Unsupported Media Type",
                "details": f"Expected application/json, got {ctype}"
            }), 415

        # auth check
        if not session.get("authenticated"):
            return jsonify({
                "reply": "Not authenticated",
                "duration": "",
                "html": None
            }), 401

        user_msg     = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        # update history
        history = session.get("history", [])
        history.append({"role": "user", "content": user_msg})

        # call Groq's chat endpoint instead of predict
        response = client.chat(
            model=os.getenv("GROQ_MODEL", "llama-2-7b-chat"),
            messages=history,
            max_tokens=512,
            temperature=0.7
        )

        # extract reply & latency
        assistant_msg = response.choices[0].message.content
        duration      = f"[{getattr(response, 'latency', 0):.2f}s]"

        # persist
        history.append({"role": "assistant", "content": assistant_msg})
        session["history"] = history

        # build HTML
        reply_html = f"<p>{assistant_msg}</p>"
        if show_sources and getattr(response, "sources", None):
            items = "".join(f"<li>{src}</li>" for src in response.sources)
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
            "details": last
        }), 500
