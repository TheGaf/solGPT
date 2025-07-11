import os
from flask import Flask, redirect, url_for
from flask_cors import CORS

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder=None,
    )
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))

    # Only allow AJAX POSTs to /chat/api
    CORS(app, resources={r"/chat/api": {"origins": "*"}}, supports_credentials=True)

    # Health check
    @app.route("/healthz")
    def healthz():
        return "OK", 200

    # Root shows the password form
    @app.route("/", methods=["GET", "POST"])
    def index():
        from flask import render_template, request, session, redirect
        if request.method == "POST":
            pw = request.form.get("password", "")
            if pw == os.getenv("SOL_GPT_PASSWORD"):
                session["authenticated"] = True
                return redirect(url_for("chat.chat_ui"))
            else:
                return render_template("index.html", error="Incorrect password"), 401
        return render_template("index.html"), 200

    # Register your chat blueprint
    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=10000)
