# main.py

import os
import logging
import traceback

from flask import Flask, redirect, url_for
from flask_cors import CORS
from config import SYSTEM_PROMPT, drive_service, FOLDER_ID, client
from routes.chat import chat_bp

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-fallback-secret")

# Allow the session cookie to be sent via fetch(credentials: 'include')
app.config.update(
    SESSION_COOKIE_SAMESITE='None',  # allow cross-site or same-site requests
    SESSION_COOKIE_SECURE=True        # cookie only over HTTPS
)

# Enable CORS (with credentials) on /chat/*
CORS(app,
     resources={r"/chat/*": {"origins": "*"}},
     supports_credentials=True)

# Register the chat blueprint
app.register_blueprint(chat_bp)

# Redirect root to the chat UI
@app.route("/")
def root():
    return redirect(url_for("chat.chat_ui"))

# Health-check endpoint
@app.route("/healthz")
def healthz():
    return {"status": "ready"}, 200

# Global error catcher
@app.errorhandler(Exception)
def catch_all(err):
    from werkzeug.exceptions import HTTPException
    if isinstance(err, HTTPException):
        return err, err.code

    logging.error("Uncaught exception:\n%s", traceback.format_exc())
    return {"error": "Server crashed", "details": str(err)}, 500

# Note: app.run() is omitted in favor of running under Gunicorn,
# which will bind to the PORT environment variable automatically.
