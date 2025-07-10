import os
from flask import Flask, redirect, url_for
from flask_cors import CORS

# Pull in any global clients or configuration you need
from config import SYSTEM_PROMPT, text_collection, drive_service, FOLDER_ID

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",   # ← make sure Flask loads index.html & sol.html
        static_folder=None
    )

    # 2) Secret key for session cookies
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))

    # 3) (Optional) CORS only on your API route if you ever host UI elsewhere
    CORS(
        app,
        resources={r"/chat": {"origins": "*"}},
        supports_credentials=True
    )

    # 4) Redirect root GET → /chat
    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("chat.chat_home"))

    # 5) Register the chat blueprint
    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)

    return app
