import requests
from app import create_app

app = create_app()
# Prefetch UI template
try:
    page_html = requests.get("https://gaf.nyc/sol.html", timeout=5).text
except:
    page_html = "<html><body>UI unavailable</body></html>"
app.page_html = page_html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
