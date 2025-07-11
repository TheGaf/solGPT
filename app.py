import os
from flask import Flask, redirect, url_for
from flask_cors import CORS

def create_app():
    # Create the Flask app, pointing at your templates folder
    app = Flask(
        __name__,
        template_folder="templates",   # ← loads index.html & sol.html from /templates
        static_folder=None
    )

    # Secret key for session management
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))

    # Enable CORS for your /chat API (if UI ever lives elsewhere)
    CORS(app, resources={r"/chat": {"origins": "*"}}, supports_credentials=True)

    # --- Health check for Render and sanity tests ---
    @app.route("/healthz", methods=["GET"])
    def healthz():
        return "OK", 200

    # --- Root redirect to chat interface ---
    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("chat.chat_home"))

    # --- Register your chat blueprint ---
    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)

    return app


# If you ever want to run it directly (not via Gunicorn), you can:
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=10000, debug=False)
