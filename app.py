import os
from flask import Flask
from routes.auth import auth_bp
from routes.chat import chat_bp

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.secret_key = os.urandom(24)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    return app
