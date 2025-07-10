import os
from flask import Flask
from flask_cors import CORS
# import blueprints, config, extensions, etc.

def create_app():
    app = Flask(__name__, static_folder=None)
    CORS(app, resources={r"/chat": {"origins": "*"}}, supports_credentials=True)
    # register blueprints, load config, init extensions...
    from routes.chat import chat_bp
    app.register_blueprint(chat_bp)
    return app
