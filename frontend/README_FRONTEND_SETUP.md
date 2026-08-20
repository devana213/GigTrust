# GigTrust Frontend — Review Version

This folder is designed to be placed directly inside your existing GigTrust project.

## Final project structure

```text
GigTrust/
├── .venv/
├── agent/
├── backend/
├── database/
├── mongo/
├── telemetry/
├── frontend/                 <-- ADD THIS FOLDER
│   ├── index.html
│   ├── dashboard.html
│   ├── styles.css
│   ├── config.js
│   ├── login.js
│   └── dashboard.js
├── .dockerignore
├── .env
├── .gitignore
├── Dockerfile
├── README.md
└── requirements.txt
```

## What this review frontend does

- Shows a GigTrust login page.
- Checks the deployed FastAPI backend before login.
- Uses temporary demo credentials.
- Opens a dashboard after login.
- Dashboard calls your real FastAPI health endpoints:
  - `/health/database`
  - `/health/mongodb`
  - `/health/cassandra`

Therefore the dashboard is genuinely connected to your deployed backend even though the marketplace cards are still demo data.

## Demo login

```text
Email: demo@gigtrust.com
Password: gigtrust123
```

## 1. Copy the folder

Unzip this package.

Copy the entire `frontend` folder into:

```text
C:\Users\Jignesh Sudheer\GigTrust\
```

So the path becomes:

```text
C:\Users\Jignesh Sudheer\GigTrust\frontend\
```

## 2. Enable CORS in FastAPI

Your browser frontend is a different origin from the Azure backend, so FastAPI must allow it.

In the Python file where you create:

```python
app = FastAPI(...)
```

add:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For a quick review-only setup, you can temporarily use:

```python
allow_origins=["*"]
```

but the explicit localhost origins are cleaner.

## 3. Rebuild/redeploy backend after CORS change

Because your Azure backend runs from a Docker image, after changing the FastAPI code you must:

```powershell
docker build -t gigtrust-api .
```

Then tag and push the image to your existing ACR, and restart/redeploy the Azure service so the new CORS configuration is active.

If your deployed backend already has CORS enabled, you can skip this step.

## 4. Run the frontend locally

Open a new PowerShell:

```powershell
cd "C:\Users\Jignesh Sudheer\GigTrust\frontend"
python -m http.server 5500
```

Then open:

```text
http://localhost:5500
```

## 5. How frontend-backend connection works

```text
Browser frontend
      |
      | fetch()
      v
FastAPI backend on Azure
      |
      +--> GET /health/database
      +--> GET /health/mongodb
      +--> GET /health/cassandra
      |
      v
Azure SQL / MongoDB / Cassandra
```

## Important

The current login is intentionally a demo login because the existing backend does not yet have a confirmed authentication API in this review setup.

For the final review, replace the hardcoded credentials with a real endpoint such as:

```text
POST /auth/login
```

and have FastAPI validate the user against Azure SQL.

The current frontend still proves frontend-to-backend integration because it actively calls the deployed backend before login and on the dashboard.
