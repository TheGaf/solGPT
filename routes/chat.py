# routes/chat.py

import logging
import os
import traceback
from io import BytesIO

from rag.drive import load_drive_docs
from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for
)
from markdown2 import markdown
from googleapiclient.http import MediaIoBaseUpload  # ← new import
from config import SYSTEM_PROMPT, client, drive_service, FOLDER_ID

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

# … chat_ui and logout unchanged …

@chat_bp.route("/api", methods=["GET", "POST", "OPTIONS"])
def chat_api():
    if request.method in ("GET", "OPTIONS"):
        return jsonify({"status": "ok"}), 200

    try:
        if not session.get("authenticated"):
            return jsonify({"reply":"Not authenticated","duration":"","html":None}), 401

        # 1) File upload path
        uploaded = request.files.get("file")
        if uploaded:
            # optional text alongside the file
            user_msg = request.form.get("message", "").strip()

            # Prepare upload payload
            media = MediaIoBaseUpload(
                uploaded.stream,
                mimetype=uploaded.mimetype,
                resumable=False
            )
            drive_file = drive_service.files().create(
                body={"name": uploaded.filename, "parents": [FOLDER_ID]},
                media_body=media,
                fields="id"
            ).execute()
            file_id = drive_file["id"]

            # Make it public
            drive_service.permissions().create(
                fileId=file_id,
                body={"role":"reader","type":"anyone"}
            ).execute()

            view_url     = f"https://drive.google.com/file/d/{file_id}/view"
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download"

            html = (
                f"<p>Uploaded <strong>{uploaded.filename}</strong></p>"
                f"<a href=\"{view_url}\" target=\"_blank\">"
                f"<img src=\"{download_url}\" "
                "style=\"max-width:200px;border-radius:6px;margin:6px 0;\"/>"
                "</a>"
            )
            return jsonify({"reply": uploaded.filename, "html": html, "duration": ""}), 200

        # 2) JSON chat path
        if not request.is_json:
            return jsonify({
                "error": "Unsupported Media Type",
                "details": "Expected multipart/form-data with file or application/json"
            }), 415

        data         = request.get_json(force=True)
        user_msg     = data.get("message", "").strip()
        show_sources = bool(data.get("show_sources", False))

        # … rest of your text/chat logic …

    except Exception:
        logging.error("Error in /chat/api:\n%s", traceback.format_exc())
        last = traceback.format_exc().splitlines()[-1]
        return jsonify({"error":"Internal server error","details":last}), 500
