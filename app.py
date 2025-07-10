import os
from flask import Flask, redirect, url_for
from flask_cors import CORS

# Load any global clients or config you need
from config import SYSTEM_PROMPT, text_collection, drive_service, FOLDER_ID

def create_app():
    # 1) Create Flask app
    app = Flask(__name__, static_folder=None)
    
    # 2) Secret key for sessions
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))
    
    # 3) Enable CORS on /chat (adjust origins as needed)
    CORS(app, resources={r"/chat": {"origins": "*"}}, supports_credentials=True)
    
    # 4) Redirect root → /chat UI
    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("chat.chat_home"))
    
    # 5) Register your chat blueprint
    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)
    
    return app
