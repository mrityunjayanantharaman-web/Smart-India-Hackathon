import json

import h3
from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.database import get_connection

router = APIRouter()


@router.get("/dashboard/dossier")
def dashboard_dossier():
    return FileResponse("frontend/dossier.html")


@router.get("/dossier-data")
def get_dossier_data(h3: str):
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
        latitude, longitude = h3.cell_to_latlng(row[0])
    except AttributeError:
        latitude, longitude = h3.h3_to_geo(row[0])

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
