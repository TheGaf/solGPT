from app import create_app

# 1) Build the Flask app
app = create_app()

# 2) If you run this file directly, launch Flask’s built-in server
if __name__ == "__main__":
    # match Render’s default port
    app.run(host="0.0.0.0", port=10000, debug=False)
