import time, logging, os, requests, markdown2
from flask import (
    Blueprint, request, jsonify, session,
    current_app, render_template
)
from config import SYSTEM_PROMPT, drive_service, FOLDER_ID
from rag.drive import load_drive_docs

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


# 1) GET /chat — serves the chat UI (sol.html)
@chat_bp.route("/", methods=["GET"])
def chat_ui():
    if not session.get("authenticated"):
        # if someone sneaks here, kick them back to login
        from flask import redirect, url_for
        return redirect(url_for("index"))
    return render_template("sol.html"), 200


# 2) POST /chat/api — your AJAX chat endpoint
@chat_bp.route("/api", methods=["POST"])
def chat_api():
    if not session.get("authenticated"):
        return jsonify({"reply":"Not authenticated","duration":"","html":None}), 401

    show = request.form.get("show_sources","true") == "true"
    session["show_sources"] = show

    # Prepare RAG contexts...
    drive_contexts, drive_sources = [], []
    if show and drive_service and FOLDER_ID:
        docs = load_drive_docs(drive_service, FOLDER_ID)
        for chunk, src in docs[:3]:
            drive_contexts.append(chunk)
            drive_sources.append(src)

    duration_str = ""
    structured_html = "⚠️ Sorry, something went wrong."

    try:
        # 1) get user message
        user_msg = request.form.get("message","").strip()
        history = session.setdefault("history", [])
        history.append({"role":"user","content":user_msg})
        session["history"] = history[-20:]

        # 2) build prompt
        user_block = user_msg
        if drive_contexts:
            snips = "\n\n".join(f"[{i+1}] {c}" for i,c in enumerate(drive_contexts))
            user_block += f"\n\nDrive Snippets:\n{snips}"

        messages = [{"role":"system","content":SYSTEM_PROMPT},
                    {"role":"user","content":user_block}] + session["history"]

        # 3) call LLM
        start = time.time()
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={"model":"llama3-8b-8192","messages":messages,"temperature":0.6},
            timeout=30
        )
        resp.raise_for_status()
        reply_md = resp.json()["choices"][0]["message"]["content"]
        duration_str = f"[{time.time()-start:.2f}s]"

        # 4) markdown → HTML
        reply_html = markdown2.markdown(
            reply_md,
            extras=["fenced-code-blocks","tables","strike","task_list"]
        )

        # 5) append sources
        sources = []
        if show and drive_sources:
            cit = "<h4>Drive Sources</h4><ul>"
            for src in dict.fromkeys(drive_sources):
                cit += f"<li>{src}</li>"
            cit += "</ul>"
            sources.append(cit)

        structured_html = reply_html + ("<hr>"+ "".join(sources) if sources else "")
        session["history"].append({"role":"assistant","content":reply_md})

    except Exception:
        logging.exception("🔥 Unhandled error in /chat/api:")

    return jsonify({"reply":structured_html,"duration":duration_str,"html":None}), 200
