import json

import h3
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ai.emissions import estimate_emissions
from backend.database import get_connection

router = APIRouter()


@router.get("/dashboard/dossier")
def dashboard_dossier():
    return FileResponse("frontend/dossier.html")


@router.get("/dossier-data")
def get_dossier_data(h3: str):
    conn = get_connection()
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if "persistent_firms_sites" not in tables:
        conn.close()
        return {
            "error": "Site not found (database not populated)",
            "h3_cell": h3,
        }

    cols = {
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'persistent_firms_sites'"
        ).fetchall()
    }
    has_pm25 = "pm25_kg" in cols
    has_co2 = "co2_tonnes" in cols

    pm25_select = "pm25_kg," if has_pm25 else "NULL AS pm25_kg,"
    co2_select = "co2_tonnes" if has_co2 else "NULL AS co2_tonnes"

    row = conn.execute(
        f"""
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
            ml_model,
            {pm25_select}
            {co2_select}
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

    shap_row = None
    if "shap_explanations" in tables:
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

    avg_frp = round(row[5], 2) if row[5] is not None else 0.0
    active_days = row[2] or 1
    source_cls = row[19] or row[11] or "Agricultural"

    pm25 = row[23]
    co2 = row[24]
    em_data = estimate_emissions(avg_frp, active_days, source_cls)
    if pm25 is None:
        pm25 = em_data["pm25_kg"]
    if co2 is None:
        co2 = em_data["co2_tonnes"]

    return {
        "h3_cell": row[0],
        "latitude": latitude,
        "longitude": longitude,
        "thermal_activity": {
            "detection_count": row[1],
            "active_days": row[2],
            "first_detection": str(row[3]),
            "last_detection": str(row[4]),
            "avg_frp": avg_frp,
            "max_frp": round(row[6], 2) if row[6] is not None else 0.0,
            "avg_brightness_temperature": round(row[7], 2) if row[7] is not None else 0.0,
            "daytime_detections": row[8],
            "nighttime_detections": row[9],
            "persistence_score": round(row[10], 3) if row[10] is not None else 0.0,
            "pm25_kg": round(float(pm25), 2) if pm25 is not None else None,
            "co2_tonnes": round(float(co2), 3) if co2 is not None else None,
        },
        "legacy_classification": {
            "classification": row[11],
            "confidence": round(row[12], 3) if row[12] is not None else 0.0,
        },
        "risk": {
            "risk_score": round(row[13], 2) if row[13] is not None else 0.0,
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
            "confidence": round(row[20], 3) if row[20] is not None else 0.0,
            "probabilities": row[21],
            "model": row[22],
        },
        "emissions": {
            "pm25_kg": round(float(pm25), 2) if pm25 is not None else None,
            "co2_tonnes": round(float(co2), 3) if co2 is not None else None,
            "assumptions": em_data["assumptions"],
        },
        "ai_explanation": {
            "prediction": shap_row[0] if shap_row else None,
            "features": explanation_features,
        },
    }
