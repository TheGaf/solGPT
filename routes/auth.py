from flask import Blueprint, request, render_template, redirect, url_for, session
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def password_gate():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == os.getenv('SOL_GPT_PASSWORD'):
            session['authenticated'] = True
            return redirect(url_for('chat.chat_home'))
    return render_template('index.html')
