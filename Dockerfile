# Use the official cloudflared image as a source for the binary
FROM cloudflare/cloudflared:latest as cloudflared-binary

# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy cloudflared binary from the official image
COPY --from=cloudflared-binary /usr/local/bin/cloudflared /usr/local/bin/cloudflared

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for persistent data
RUN mkdir -p /app/data

# Create directory for frontend to avoid crash (since it's hardcoded in main.py)
# main.py expects FRONTEND_DIR at ../../../Cloudflare_frontend relative to main.py
# If app is in /app, main.py is in /app, so FRONTEND_DIR is /Cloudflare_frontend
RUN mkdir -p /Cloudflare_frontend && touch /Cloudflare_frontend/index.html

# Expose the default port
# This will be overridden by the APP_PORT env var at runtime
EXPOSE 1231

# Command to run the application
CMD ["python", "main.py"]
