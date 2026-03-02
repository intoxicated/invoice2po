"""
Local development server — runs all Cloud Function endpoints in one process.
Use this for local testing before deploying to GCP.

Run: python local_server.py
Endpoints:
  POST http://localhost:8080/identify       -> identify_and_generate
  POST http://localhost:8080/generate_po    -> generate_po
  POST http://localhost:8080/sync_to_thrive -> sync_to_thrive
"""

import sys
from flask import Flask, request, Response

# Import the Cloud Function handlers
from main import identify_and_generate as identify_handler
from po_generator import generate_po as generate_po_handler
from thrive_sync import sync_to_thrive as sync_to_thrive_handler

app = Flask(__name__)


def _run_handler(handler):
    """Wrap functions_framework handler for Flask."""
    result = handler(request)
    if isinstance(result, tuple):
        body, status, headers = result
        return Response(body, status=status, headers=dict(headers or {}))
    return result


@app.route("/identify", methods=["POST"])
def identify():
    return _run_handler(identify_handler)


@app.route("/generate_po", methods=["POST"])
def generate_po():
    return _run_handler(generate_po_handler)


@app.route("/sync_to_thrive", methods=["POST"])
def sync_to_thrive():
    return _run_handler(sync_to_thrive_handler)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "kpopnara-cloud-functions-local"}, 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"Local Cloud Functions server: http://localhost:{port}")
    print("  POST /identify       - Product identification")
    print("  POST /generate_po    - PO document generation")
    print("  POST /sync_to_thrive - Thrive sync")
    app.run(host="0.0.0.0", port=port, debug=True)
