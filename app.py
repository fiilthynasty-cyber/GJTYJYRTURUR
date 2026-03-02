from flask import Flask, jsonify, request
from flask_cors import CORS
import os

# Create Flask app
app = Flask(__name__)

# Enable CORS (allows frontend to connect)
CORS(app)

# -------------------
# ROOT ROUTE
# -------------------
@app.route("/")
def home():
    return "Backend is live!"

# -------------------
# TEST API ROUTE
# -------------------
@app.route("/api/hello", methods=["GET"])
def hello():
    return jsonify({
        "status": "success",
        "message": "Hello from backend!"
    })

# -------------------
# EXAMPLE POST ROUTE
# -------------------
@app.route("/api/data", methods=["POST"])
def receive_data():
    data = request.json

    return jsonify({
        "status": "received",
        "you_sent": data
    })

# -------------------
# REQUIRED FOR RENDER
# -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
