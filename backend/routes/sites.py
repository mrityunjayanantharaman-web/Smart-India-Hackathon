import h3
from fastapi import APIRouter

from ai.emissions import estimate_emissions
from backend.database import get_connection, get_firms_summary

router = APIRouter()


@router.get("/persistent-sites")
def get_persistent_sites_endpoint():
    conn = get_connection()
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if "persistent_firms_sites" not in tables:
        conn.close()
        return {"count": 0, "persistent_sites": []}

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

    rows = conn.execute(
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
            source_scores,
            ml_classification,
            ml_confidence,
            ml_probabilities,
            ml_model,
            {pm25_select}
            {co2_select}
        FROM persistent_firms_sites
        ORDER BY persistence_score DESC
        """
    ).fetchall()
    conn.close()

    sites = []
    for row in rows:
        avg_frp = round(row[5], 2) if row[5] is not None else 0.0
        active_days = row[2] or 1
        source_cls = row[14] or row[11] or "Agricultural"

        pm25 = row[18]
        co2 = row[19]
        if pm25 is None or co2 is None:
            em = estimate_emissions(avg_frp, active_days, source_cls)
            pm25 = em["pm25_kg"]
            co2 = em["co2_tonnes"]

        sites.append(
            {
                "h3_cell": row[0],
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
                "classification": row[11],
                "classification_confidence": round(row[12], 3) if row[12] is not None else 0.0,
                "source_scores": row[13],
                "ml_classification": row[14],
                "ml_confidence": round(row[15], 3) if row[15] is not None else 0.0,
                "ml_probabilities": row[16],
                "ml_model": row[17],
                "pm25_kg": round(float(pm25), 2) if pm25 is not None else None,
                "co2_tonnes": round(float(co2), 3) if co2 is not None else None,
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
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if "persistent_firms_sites" not in tables:
        conn.close()
        return {"count": 0, "risk_sites": []}

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

    rows = conn.execute(
        f"""
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
            location_name,
            {pm25_select}
            {co2_select}
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

        avg_frp = round(row[3], 2) if row[3] is not None else 0.0
        active_days = row[2] or 1
        source_cls = row[12] or row[6] or "Agricultural"

        pm25 = row[21]
        co2 = row[22]
        if pm25 is None or co2 is None:
            em = estimate_emissions(avg_frp, active_days, source_cls)
            pm25 = em["pm25_kg"]
            co2 = em["co2_tonnes"]

        sites.append(
            {
                "h3_cell": h3_cell,
                "latitude": latitude,
                "longitude": longitude,
                "detection_count": row[1],
                "active_days": row[2],
                "avg_frp": avg_frp,
                "max_frp": round(row[4], 2) if row[4] is not None else 0.0,
                "persistence_score": round(row[5], 3) if row[5] is not None else 0.0,
                "classification": row[6],
                "classification_confidence": round(row[7], 3) if row[7] is not None else 0.0,
                "risk_score": round(row[8], 2) if row[8] is not None else 0.0,
                "priority": row[9],
                "first_detection": str(row[10]),
                "last_detection": str(row[11]),
                "ml_classification": row[12],
                "ml_confidence": round(row[13], 3) if row[13] is not None else 0.0,
                "ml_probabilities": row[14],
                "ml_model": row[15],
                "nightfire_match": bool(row[16]),
                "nightfire_matches": row[17],
                "no2_mean": row[18],
                "no2_max": row[19],
                "location_name": row[20] or "",
                "pm25_kg": round(float(pm25), 2) if pm25 is not None else None,
                "co2_tonnes": round(float(co2), 3) if co2 is not None else None,
            }
        )

    return {
        "count": len(sites),
        "risk_sites": sites,
    }
