# AgniNetra

AgniNetra is a national thermal intelligence platform that turns satellite fire detections and supporting evidence into persistent-site intelligence, risk scores, dossiers, and investigation reports.

## Project Structure

```text
AgniNetra/
├── ai/                         Machine-learning training, validation, and explanations
├── backend/                    FastAPI application and DuckDB access layer
│   ├── database.py             Database initialization and queries
│   ├── main.py                 Application composition and router registration
│   ├── models.py               Request and response models
│   └── routes/                 Feature-specific API routers
│       ├── system.py           Root and health endpoints
│       ├── thermal_events.py   Thermal-event ingestion and listing
│       ├── sites.py            Persistent, FIRMS, and risk-site features
│       ├── dossiers.py         Investigation dossier data and page route
│       └── reports.py          PDF investigation report downloads
├── data/                       Ingestion, processing, classification, and reports
│   ├── raw/                    Local source data; ignored by Git
│   └── processed/              Local database and generated outputs; ignored by Git
├── frontend/                   Static dashboard files served by FastAPI
│   ├── index.html              Main intelligence dashboard
│   ├── dossier.html            Site dossier view
│   └── tokens.css              Shared design tokens
├── hardware/                   Hardware notes and deployment documentation
├── requirements.txt            Python dependencies
├── run_demo.bat                Windows demo launcher and smoke test
├── recoverment.txt             Recovery and restart instructions
└── .env.example                Environment variable template
```

## Requirements

- Windows 10 or later
- Python 3.11 or later
- A populated `data/processed/agninetra.duckdb` database for the full dashboard
- A FIRMS API key only when running the live ingestion scripts

## First-Time Setup

Open PowerShell in the project directory:

```powershell
cd "C:\Users\<your-user>\Downloads\SIH\AgniNetra"
```

Create a virtual environment if `venv` does not exist:

```powershell
python -m venv venv
```

Activate the backend environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, allow scripts for the current user and activate again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and replace placeholder values before running any live data ingestion:

```powershell
Copy-Item .env.example .env
```

## Run the Application

### Option 1: Demo launcher

The launcher checks the local database, starts the backend, runs the smoke test, and prints the dashboard URL:

```powershell
.\run_demo.bat
```

### Option 2: Start the backend manually

Activate the environment first, then run:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The frontend does not need a separate Node.js activation command. It is static HTML, CSS, and JavaScript served by the FastAPI backend.

Open these URLs after startup:

- Dashboard: http://127.0.0.1:8000/dashboard/
- Site dossier: http://127.0.0.1:8000/dashboard/dossier.html
- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

Stop the development server with `Ctrl+C`.

## API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service status |
| `GET` | `/health` | Health check |
| `GET` | `/firms-summary` | FIRMS summary statistics |
| `GET` | `/persistent-sites` | Persistent thermal sites |
| `GET` | `/risk-sites` | Ranked risk sites |
| `GET` | `/dossier-data?h3=<cell>` | Dossier data for an H3 cell |
| `GET` | `/thermal-events` | Stored thermal events |
| `POST` | `/thermal-event` | Store a thermal event |
| `GET` | `/report/<h3-cell>` | Download a generated PDF report |

## Data Pipeline

The scripts in `data/` are intended to be run in sequence when rebuilding the local data products. The existing processed database can be used directly for the demo. Keep downloaded source data, generated databases, and reports in the ignored `data/raw/` and `data/processed/` directories.

Run the built-in validation after starting the backend:

```powershell
python data\demo_smoke_test.py
```

## Troubleshooting

- **`venv` is not recognized:** run commands from the `AgniNetra` directory and use `\.\venv\Scripts\python.exe`.
- **Port 8000 is busy:** stop the existing process or use another port, for example `python -m uvicorn backend.main:app --port 8001`.
- **Dashboard data is empty:** confirm `data/processed/agninetra.duckdb` exists and rebuild or restore the processed data.
- **PowerShell activation is blocked:** use the `Set-ExecutionPolicy` command in the setup section, or run the virtual-environment Python directly.
- **A report is missing:** generate the report for the requested H3 cell and place the PDF under `data/processed/pdf_reports/`.

## Recovery

See [recoverment.txt](recoverment.txt) for the short restart and recovery checklist.