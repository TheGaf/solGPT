# main.py
import requests
from app import create_app

# 1) Build the Flask app
app = create_app()

# 2) Prefetch your frontend HTML (sol.html) into app.page_html
try:
    ui_response = requests.get("sol.html", timeout=5)
    ui_response.raise_for_status()
    app.page_html = ui_response.text
except Exception:
    app.page_html = "<!DOCTYPE html><html><body><h1>UI unavailable</h1></body></html>"

# 3) If you run this file directly, launch Flask’s built-in server
if __name__ == "__main__":
    # match Render’s default port
    app.run(host="0.0.0.0", port=10000, debug=False)
