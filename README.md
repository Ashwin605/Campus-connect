# 🚀 CampusConnect Enterprise

![Version](https://img.shields.io/badge/version-2.0.0--beta-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.1.1-green.svg)
![Socket.IO](https://img.shields.io/badge/socket.io-realtime-orange.svg)
![License](https://img.shields.io/badge/license-MIT-purple.svg)

> **The next-generation, AI-driven Campus Ambassador Management Platform.**  
> Engineered for massive scale, gamified viral growth, and real-time community engagement.

---

## ✨ Enterprise Features

### 🤖 AI-Powered Scoring Engine
Submissions are evaluated autonomously via advanced AI analysis, returning structured metrics:
- **Grammar & Tone Analysis**
- **Brand Alignment Verification**
- **Creative Impact Scoring**

### ⚡ Real-Time Global Activity Feed (WebSockets)
Powered by `Flask-SocketIO` and Eventlet, every action on the platform (task completion, level ups, badges) is broadcast instantly to all connected users, simulating a highly active, living platform ecosystem.

### 🪙 CampusCoins (CC) Gamified Economy
Built-in tokenized reward system where Ambassadors earn **CampusCoins (CC)**. 
- Integrated **Wallet Interface** for real-world redemptions (e.g., Campus Hoodies, Amazon Gift Cards).
- Dynamic leveling system (Bronze → Silver → Gold → Diamond) tied to CC yield.

### 💎 Ultra-Minimalist "Clinical Luxury" UI
- Custom-built **Glassmorphism** aesthetic with deep frosted glass (`backdrop-filter`).
- Dynamic **Ambient Background Orbs** that shift based on system state.
- Highly optimized high-contrast Dark and Light modes.

### 🔐 Production-Ready Architecture
- **Gunicorn + Eventlet** asynchronous WSGI server.
- **Flask-Migrate** for seamless Alembic schema upgrades.
- **CSRF Protection** injected across all secure endpoints.
- `.env` abstraction for database URIs and secret keys.

---

## 🛠 Tech Stack

| Domain | Technology |
| :--- | :--- |
| **Backend Framework** | Flask, Python 3 |
| **Database ORM** | Flask-SQLAlchemy, SQLite (Dev) / PostgreSQL (Prod) |
| **Real-Time Networking** | Flask-SocketIO, Eventlet WSGI |
| **Frontend Rendering** | Jinja2, HTML5, Vanilla CSS3 (Custom Design System) |
| **Data Visualization** | Chart.js (Interactive Analytics) |
| **Authentication** | Flask-Login, Werkzeug Security (Bcrypt) |

---

## 🚀 Quick Start (Local Development)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/CampusConnect.git
cd CampusConnect
```

### 2. Configure Virtual Environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Create a `.env` file in the root directory (refer to `.env.example`):
```env
SECRET_KEY=super-secure-random-key
FLASK_ENV=development
```

### 5. Initialize & Run
```bash
# Start the asynchronous server (Watchdog & Eventlet enabled)
python app.py
```
*Navigate to `http://127.0.0.1:8080` in your browser.*

---

## 🌍 Production Deployment

This application is configured for immediate PaaS deployment (Render, Heroku, AWS).

1. Set `FLASK_ENV=production` in your server environment.
2. Provide a valid `DATABASE_URL` (PostgreSQL recommended via `psycopg2-binary`).
3. The server will utilize the pre-configured `Procfile`:
   ```Procfile
   web: gunicorn --worker-class eventlet -w 1 app:app
   ```
4. Run Database Migrations:
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

---

## 📂 Project Structure

```text
CampusConnect/
├── app.py                  # Core Application & WebSocket Event Hub
├── models.py               # SQLAlchemy Database Schemas & Relationships
├── config.py               # Environment & Security Configurations
├── requirements.txt        # Production Dependencies
├── Procfile                # WSGI Server Instructions
├── static/
│   ├── css/style.css       # Global Design System & Glassmorphism Tokens
│   └── uploads/            # Secure Asset Storage
└── templates/              # Jinja2 Layouts
    ├── base.html           # Master Layout & Ambient UI Injectors
    ├── auth/               # Secure Login/Register flows
    ├── amb/                # Ambassador Dashboard & Wallet UI
    └── org/                # Organization Analytics & Management
```

---

*Designed and developed to push the boundaries of hackathon-grade web applications.* 🚀
