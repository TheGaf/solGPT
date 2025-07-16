# app.py

import os
import logging
import traceback

from flask import Flask
from flask_cors import CORS
from config import GROQ_API_KEY  # just to force a crash early if missing
from routes.chat import chat_bp

# --- Initialize Flask ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev‐fallback-secret")  # for sessions

# --- CORS (if your UI is served on the same domain you may not need this) ---
CORS(app,
     resources={r"/chat/*": {"origins": "*"}},
     supports_credentials=True)

# --- Register Blueprints ---
app.register_blueprint(chat_bp)

# --- Health Endpoint for whole app ---
@app.route("/healthz")
def healthz():
    return {"status": "ready"}, 200

# --- Global Error Catcher (just in case!) ---
@app.errorhandler(Exception)
def catch_all(err):
    logging.error("Uncaught exception:\n%s", traceback.format_exc())
    return {"error": "Server crashed", "details": str(err)}, 500


if __name__ == "__main__":
    # Force early failure if your key is missing
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in environment")

    port = int(os.environ.get("PORT", 5000))
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting app on port %d", port)
    app.run(host="0.0.0.0", port=port)
