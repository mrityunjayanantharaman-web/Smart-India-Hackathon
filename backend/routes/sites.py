import h3
from fastapi import APIRouter

from backend.database import get_connection, get_firms_summary

router = APIRouter()


@router.get("/persistent-sites")
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


@router.get("/firms-summary")
def get_firms_summary_endpoint():
    return get_firms_summary()


@router.get("/risk-sites")
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
