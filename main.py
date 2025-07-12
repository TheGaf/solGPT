# main.py

import os
import logging
import traceback

from flask import Flask, redirect
from flask_cors import CORS
from config import SYSTEM_PROMPT, drive_service, FOLDER_ID, client
from routes.chat import chat_bp

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev‐fallback-secret")

# Session cookie settings
app.config.update(
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=True,
)

# Enable CORS on chat routes
CORS(app, resources={r"/chat/*": {"origins": "*"}}, supports_credentials=True)

# **Mount the chat blueprint at /chat**
app.register_blueprint(chat_bp, url_prefix="/chat")

@app.route("/")
def root():
    # direct root callers to /chat/ 
    return redirect("/chat/")

@app.route("/healthz")
def healthz():
    return {"status": "ready"}, 200

@app.errorhandler(Exception)
def catch_all(err):
    from werkzeug.exceptions import HTTPException
    if isinstance(err, HTTPException):
        return err, err.code

    logging.error("Uncaught exception:\n%s", traceback.format_exc())
    return {"error": "Server crashed", "details": str(err)}, 500
