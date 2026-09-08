from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.database import initialize_database
from backend.routes import dossiers, reports, sites, system, thermal_events


app = FastAPI(
    title="AgniNetra",
    description="National Thermal Intelligence Platform",
    version="0.1.0",
)

initialize_database()

app.include_router(system.router)
app.include_router(thermal_events.router)
app.include_router(sites.router)
app.include_router(dossiers.router)
app.include_router(reports.router)
app.mount("/dashboard", StaticFiles(directory="frontend", html=True), name="dashboard")
