import os
from flask import Flask, redirect, url_for
from flask_cors import CORS

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",   # ← loads index.html & sol.html from /templates
        static_folder=None
    )
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))

    # Allow browser → /chat POSTs (if you ever host UI elsewhere)
    CORS(app, resources={r"/chat": {"origins": "*"}}, supports_credentials=True)

    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("chat.chat_home"))

    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)

    return app
