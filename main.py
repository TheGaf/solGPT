from app import create_app

app = create_app()

if __name__ == "__main__":
    # in dev, use Flask’s built-in server on port 10000
    app.run(host="0.0.0.0", port=10000, debug=False)
