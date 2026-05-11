"""Token Forums — Flask app entry point."""

import os
from flask import Flask, jsonify, send_from_directory

from forums_api import forums_bp

app = Flask(__name__, static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "forums-dev")

app.register_blueprint(forums_bp)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "forums.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8084, debug=False, use_reloader=False)
