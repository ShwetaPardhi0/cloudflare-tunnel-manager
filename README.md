# Cloudflare Tunnel Manager

A high-performance, multi-tunnel management dashboard that allows you to expose local services to the internet instantly using Cloudflare’s tunneling technology. It provides a unified interface to manage, monitor, and scale multiple concurrent tunnels with real-time feedback and production-grade UX.

---

## 🎬 Demo

- Start a tunnel on any local port (e.g., `3000`)
- Instantly get a public URL
- Handle failures with real-time error feedback and retry

> *(Add GIF or screenshots here for better visualization)*

---

## 💡 Why this project?

Managing local tunnels at scale is often messy and error-prone. Tools exist to expose a single service, but handling multiple tunnels with proper visibility, control, and error handling requires a more structured approach.

This project demonstrates how to build a production-style system that handles:
- **Concurrent tunnel orchestration**: Run multiple tunnels independently.
- **Asynchronous process management**: Non-blocking log parsing and process control.
- **Real-time UI synchronization**: Polling-based dashboard updates.
- **Resilient error recovery**: Automated health checks, rate limiting, and graceful shutdowns.

---

## 🚀 Overview

Exposing local development environments or private services traditionally requires port forwarding or complex VPN setups. This project simplifies that by:

- **Managing Multiple Tunnels**: Run and monitor several tunnels on different ports simultaneously.
- **Resource-Oriented Tracking**: Each tunnel is assigned a unique UUID for independent lifecycle management.
- **Stability First**: Built-in pre-flight checks, watchdog mechanisms, and **graceful shutdown** handling to ensure no orphaned processes are left running.

---

## ✨ Key Features

- **Multi-Tunnel Dashboard**  
  A premium glassmorphism UI to view and manage all active tunnels in one place.

- **Advanced Monitoring (Prometheus)**  
  Real-time telemetry via a dedicated `/metrics` endpoint including:
  - **Uptime & Active Count**: Live gauges for system and tunnel health.
  - **Start Duration**: Connection establishment latency histograms.
  - **Error Tracking**: Counters for watchdog timeouts and process exit codes.

- **Production Observability**  
  Built for scale with enterprise-grade tracing:
  - **Structured JSON Logging**: Machine-readable logs (ready for ELK/Datadog).
  - **Request Correlation**: Unified `X-Correlation-ID` across API and background traces.
  - **Privacy First**: Automated redaction of sensitive tokens and credentials.

- **Security & Reliability**  
  - **Rate Limiting**: Built-in protection (5 requests/min).
  - **Graceful Shutdown**: Automated cleanup of all tunnels on exit.
  - **Isolation**: Unique UUIDs for every tunnel process.

- **Smart Retries**  
  One-click retry for failed tunnels with safe state reset and auto-cleanup.

- **Persistent Tunnel Tracking**  
  SQLite integration ensures tunnel history and logs are preserved across server restarts.

---

## 🧩 Architecture Flow

```text
Frontend (SPA)
    ↓
FastAPI Backend (with Lifespan Hooks)
    ↓
cloudflared Process (Subprocess)
    ↓
Local Application (localhost:port)
```

---

## 🏗️ System Architecture

The system follows a modular, service-oriented architecture:

1. **Frontend (SPA)**  
   Vanilla JavaScript with real-time polling (2-second intervals) to sync UI with backend state.

2. **REST API (FastAPI)**  
   Resource-based endpoints (`/api/tunnel`, `/api/health`) for managing lifecycle and monitoring.

3. **Tunnel Service**  
   Handles `cloudflared` subprocesses, async log parsing, and unified metrics tracking.

4. **Observability & Monitoring**  
   Prometheus-client integration and context-aware structured JSON logging.

5. **Configuration Layer**  
   Environment-driven setup using `pydantic-settings` and `.env` files.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic (v2), Asyncio
- **Config**: Pydantic Settings, Dotenv
- **Database**: SQLite (via SQLAlchemy + aiosqlite) for persistence
- **Monitoring**: Prometheus (via `prometheus-client`)
- **Logging**: Structured JSON with Correlation ID tracing
- **Containerization**: Docker, Docker Compose
- **Binary**: `cloudflared` (Cloudflare Tunnel CLI)
- **Frontend**: HTML5, CSS3 (Glassmorphism UI), Vanilla JavaScript (ES6+)
- **State Management**: SQLite persistence with in-memory sync

---

## ⚙️ Setup Instructions

### Prerequisites

- Install `cloudflared`:  
  [Cloudflare Tunnel Setup Guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started-guide/local-setup/)
- Python 3.9+

---

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/cloudflare-tunnel-manager.git
   cd cloudflare-tunnel-manager
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Adjust APP_PORT or DATABASE_URL if needed
   ```

---

## 🐳 Docker Setup (Recommended)

Running with Docker is the fastest way to get started with full persistence.

1. **Start the application**
   ```bash
   docker compose up --build -d
   ```

2. **View live logs**
   ```bash
   docker compose logs -f
   ```

3. **Stop the application**
   ```bash
   docker compose down
   ```

---

## ⚙️ Manual Setup (Development)

---

## 📖 Usage Guide

1. **Start the backend server**
   ```bash
   # From the project root
   cd backend
   python3 main.py  # Or: python3 -m uvicorn main:app --port 1231 --reload
   ```

2. **Open dashboard**
   Navigate to [http://localhost:1231](http://localhost:1231) in your browser.

3. **Create a tunnel**
   - Enter your app’s port (e.g., 3000, 8000).
   - Click **Start Tunnel**.
   - Monitor status (⏳ → ✅).
   - Once connected, copy the public URL and share it!

4. **Monitor System Health**  
   - Visit [http://localhost:1231/metrics](http://localhost:1231/metrics) for Prometheus telemetry.
   - Visit [http://localhost:1231/api/health](http://localhost:1231/api/health) for a high-level health report.

5. **View Structured Logs**  
   Logs are emitted to stdout in JSON format. Use `docker compose logs -f` or standard pipe tools.

---

## 📸 Screenshots

- Dashboard view
- Active tunnel state
- Error + toast notification
- Health Metrics JSON

---

## ⚠️ Security & Limitations

- **Backend Security**: Fully implemented via Bearer Token authentication. Any request to manage tunnels requires a valid `API_TOKEN` (configured in `.env`).
- **Frontend State**: The current SPA UI is a development-first dashboard. It does not currently store or prompt for the API token.
- **Port Visibility**: Intended for local development use only.

---

- **Frontend Auth**: Add a login screen or token input to the UI.
- **Advanced UI**: Real-time log streaming via WebSockets.
- **Scaling**: Support for persistent Cloudflare Named Tunnels.

---

## ❤️ Acknowledgment

Built as a real-world system design project to simulate production-grade developer tooling and service patterns.


