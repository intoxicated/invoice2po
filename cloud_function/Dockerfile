# Cloud Functions 2nd gen typically uses the built-in Python runtime.
# This Dockerfile is for local testing or custom deployment.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Local: run all endpoints (identify, generate_po, sync_to_thrive)
EXPOSE 8080
CMD ["python", "local_server.py"]
