# app.py
import os
from flask import Flask, redirect, url_for
from flask_cors import CORS

def create_app():
    # 1) Create the Flask application
    #    We disable static_folder (we serve everything via page_html)
    #    and point template_folder at your templates dir so index.html works.
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder=None
    )

    # 2) Secret key for session cookies
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))

    # 3) (Optional) CORS only on /chat if you ever host UI elsewhere
    CORS(
        app,
        resources={r"/chat": {"origins": "*"}},
        supports_credentials=True
    )

    # 4) Redirect root GET → /chat
    @app.route("/", methods=["GET"])
    def root():
        # when someone hits “/” send them to your chat UI
        return redirect(url_for("chat.chat_home"))

    # 5) Register your chat blueprint
    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)

    return app
