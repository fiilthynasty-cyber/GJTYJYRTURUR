from flask import Flask, jsonify, request
from flask_cors import CORS
import os

# Create Flask app
app = Flask(__name__)

# Enable CORS
CORS(app)

# -------------------
# ROOT ROUTE
# -------------------
@app.route("/")
def home():
    return "Backend is live!"

# -------------------
# HEALTH CHECK
# -------------------
@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# -------------------
# GET LEADS (FIXED)
# -------------------
@app.route("/api/getLeads", methods=["POST"])
def get_leads():
    data = request.json
    return jsonify({
        "status": "success",
        "leads": [],
        "message": "Leads endpoint working",
        "received": data
    })

# -------------------
# START SCAN (FIXED)
# -------------------
@app.route("/api/startScan", methods=["POST"])
def start_scan():
    data = request.json
    return jsonify({
        "status": "scan_started",
        "message": "Scan started successfully",
        "received": data
    })

# -------------------
# REQUIRED FOR RENDER
# -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)