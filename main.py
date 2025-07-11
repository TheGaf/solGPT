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

# Enable CORS on the chat endpoints
CORS(app,
     resources={r"/chat/*": {"origins": "*"}},
     supports_credentials=True)

# Mount your /chat blueprint
app.register_blueprint(chat_bp)

# Redirect root to the chat UI
@app.route("/")
def root():
    return redirect(url_for("chat.chat_ui"))

# Health-check endpoint
@app.route("/healthz")
def healthz():
    return {"status": "ready"}, 200

# Global error catcher for everything else
@app.errorhandler(Exception)
def catch_all(err):
    # Do not mask 404s raised by Flask
    from werkzeug.exceptions import HTTPException
    if isinstance(err, HTTPException):
        return err, err.code

    logging.error("Uncaught exception:\n%s", traceback.format_exc())
    return {"error": "Server crashed", "details": str(err)}, 500


if __name__ == "__main__":
    # Fail fast if the API key is missing
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not set in environment")

    port = int(os.environ.get("PORT", 5000))
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting app on port %d", port)
    app.run(host="0.0.0.0", port=port)
