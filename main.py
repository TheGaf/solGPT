import requests
from app import create_app

# 1) Build the app
app = create_app()

# 2) Prefetch your UI HTML
try:
    app.page_html = requests.get("https://gaf.nyc/sol.html", timeout=5).text
except:
    app.page_html = "<!DOCTYPE html><html><body><h1>UI unavailable</h1></body></html>"

# 3) If run directly, launch Flask’s dev server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
