import json
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import h3

from backend.database import (
    get_firms_summary,
    get_connection,
    initialize_database,
    insert_thermal_event,
    list_thermal_events,
)
from backend.models import ThermalEvent


app = FastAPI(
    title="AgniNetra",
    description="National Thermal Intelligence Platform",
    version="0.1.0",
)

@app.get("/dashboard/dossier")
def dashboard_dossier():
    return FileResponse("frontend/dossier.html")


@app.get("/report/{h3}")
def download_report(h3: str):
    report_path = f"data/processed/pdf_reports/{h3}.pdf"

    if not os.path.exists(report_path):
        return {
            "error": "Report not found",
            "h3_cell": h3,
        }

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=f"AgniNetra_{h3}_Investigation_Report.pdf",
    )


app.mount("/dashboard", StaticFiles(directory="frontend", html=True), name="dashboard")

initialize_database()


@app.get("/")
def root():
    return {
        "system": "AgniNetra",
        "status": "online",
        "message": "From satellite fire dots to real-world action.",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.post("/thermal-event")
def create_thermal_event(event: ThermalEvent):
    h3_cell = h3.latlng_to_cell(event.latitude, event.longitude, 8)
    stored_event = insert_thermal_event(event.model_dump(), h3_cell)
    return {
        "message": "Thermal event stored successfully",
        **stored_event,
    }


@app.get("/thermal-events")
def get_thermal_events():
    return {
        "events": list_thermal_events(),
    }


@app.get("/persistent-sites")
def get_persistent_sites_endpoint():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            h3_cell,
            detection_count,
            active_days,
            first_detection,
            last_detection,
            avg_frp,
            max_frp,
            avg_brightness_temperature,
            daytime_detections,
            nighttime_detections,
            persistence_score,
            classification,
            classification_confidence,
            source_scores,
            ml_classification,
            ml_confidence,
            ml_probabilities,
            ml_model
        FROM persistent_firms_sites
        ORDER BY persistence_score DESC
        """
    ).fetchall()
    conn.close()

    sites = []
    for row in rows:
        sites.append(
            {
                "h3_cell": row[0],
                "detection_count": row[1],
                "active_days": row[2],
                "first_detection": str(row[3]),
                "last_detection": str(row[4]),
                "avg_frp": round(row[5], 2),
                "max_frp": round(row[6], 2),
                "avg_brightness_temperature": round(row[7], 2),
                "daytime_detections": row[8],
                "nighttime_detections": row[9],
                "persistence_score": round(row[10], 3),
                "classification": row[11],
                "classification_confidence": round(row[12], 3),
                "source_scores": row[13],
                "ml_classification": row[14],
                "ml_confidence": round(row[15], 3),
                "ml_probabilities": row[16],
                "ml_model": row[17],
            }
        )

    return {
        "count": len(sites),
        "persistent_sites": sites,
    }


@app.get("/firms-summary")
def get_firms_summary_endpoint():
    return get_firms_summary()


@app.get("/risk-sites")
def get_risk_sites():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            h3_cell,
            detection_count,
            active_days,
            avg_frp,
            max_frp,
            persistence_score,
            classification,
            classification_confidence,
            risk_score,
            priority,
            first_detection,
            last_detection,
            ml_classification,
            ml_confidence,
            ml_probabilities,
            ml_model,
            nightfire_match,
            nightfire_matches,
            no2_mean,
            no2_max,
            location_name
        FROM persistent_firms_sites
        ORDER BY risk_score DESC
        """
    ).fetchall()
    conn.close()

    sites = []
    for row in rows:
        h3_cell = row[0]
        try:
            latitude, longitude = h3.cell_to_latlng(h3_cell)
        except AttributeError:
            latitude, longitude = h3.h3_to_geo(h3_cell)

        sites.append(
            {
                "h3_cell": h3_cell,
                "latitude": latitude,
                "longitude": longitude,
                "detection_count": row[1],
                "active_days": row[2],
                "avg_frp": round(row[3], 2),
                "max_frp": round(row[4], 2),
                "persistence_score": round(row[5], 3),
                "classification": row[6],
                "classification_confidence": round(row[7], 3),
                "risk_score": round(row[8], 2),
                "priority": row[9],
                "first_detection": str(row[10]),
                "last_detection": str(row[11]),
                "ml_classification": row[12],
                "ml_confidence": round(row[13], 3),
                "ml_probabilities": row[14],
                "ml_model": row[15],
                "nightfire_match": bool(row[16]),
                "nightfire_matches": row[17],
                "no2_mean": row[18],
                "no2_max": row[19],
                "location_name": row[20] or "",
            }
        )

    return {
        "count": len(sites),
        "risk_sites": sites,
    }


@app.get("/dossier-data")
def get_dossier_data(h3: str):
    import h3 as h3_module

    conn = get_connection()
    row = conn.execute(
        """
        SELECT
            h3_cell,
            detection_count,
            active_days,
            first_detection,
            last_detection,
            avg_frp,
            max_frp,
            avg_brightness_temperature,
            daytime_detections,
            nighttime_detections,
            persistence_score,
            classification,
            classification_confidence,
            risk_score,
            priority,
            nightfire_match,
            nightfire_matches,
            no2_mean,
            no2_max,
            ml_classification,
            ml_confidence,
            ml_probabilities,
            ml_model
        FROM persistent_firms_sites
        WHERE h3_cell = ?
        LIMIT 1
        """,
        [h3],
    ).fetchone()

    if row is None:
        conn.close()
        return {
            "error": "Site not found",
            "h3_cell": h3,
        }

    shap_row = conn.execute(
        """
        SELECT
            prediction,
            explanations
        FROM shap_explanations
        WHERE h3_cell = ?
        LIMIT 1
        """,
        [h3],
    ).fetchone()
    conn.close()

    if shap_row and isinstance(shap_row[1], str):
        explanation_features = json.loads(shap_row[1])
    else:
        explanation_features = shap_row[1] if shap_row else []

    try:
            latitude, longitude = h3_module.cell_to_latlng(row[0])
    except AttributeError:
            latitude, longitude = h3_module.h3_to_geo(row[0])

    return {
        "h3_cell": row[0],
        "latitude": latitude,
        "longitude": longitude,
        "thermal_activity": {
            "detection_count": row[1],
            "active_days": row[2],
            "first_detection": str(row[3]),
            "last_detection": str(row[4]),
            "avg_frp": round(row[5], 2),
            "max_frp": round(row[6], 2),
            "avg_brightness_temperature": round(row[7], 2),
            "daytime_detections": row[8],
            "nighttime_detections": row[9],
            "persistence_score": round(row[10], 3),
        },
        "legacy_classification": {
            "classification": row[11],
            "confidence": round(row[12], 3),
        },
        "risk": {
            "risk_score": round(row[13], 2),
            "priority": row[14],
        },
        "multi_source_evidence": {
            "nightfire_match": bool(row[15]),
            "nightfire_matches": row[16],
            "no2_mean": row[17],
            "no2_max": row[18],
        },
        "ml_classification": {
            "classification": row[19],
            "confidence": round(row[20], 3),
            "probabilities": row[21],
            "model": row[22],
        },
        "ai_explanation": {
            "prediction": shap_row[0] if shap_row else None,
            "features": explanation_features,
        },
    }