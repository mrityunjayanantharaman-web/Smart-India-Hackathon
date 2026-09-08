def calculate_risk_score(
    persistence_score,
    detection_count,
    avg_frp,
    max_frp,
    classification
):
    """Calculate a prototype 0-100 thermal risk score."""
    persistence_risk = min(persistence_score, 1.0) * 30
    detection_risk = min(detection_count / 10.0, 1.0) * 20
    frp_risk = min(avg_frp / 50.0, 1.0) * 20
    peak_risk = min(max_frp / 100.0, 1.0) * 15

    source_risk = {
        "Industrial": 15,
        "Flare": 15,
        "Wildfire": 12,
        "Agricultural": 7,
        "Other": 3
    }.get(classification, 3)

    total_score = (
        persistence_risk
        + detection_risk
        + frp_risk
        + peak_risk
        + source_risk
    )
    total_score = round(min(total_score, 100), 2)

    if total_score >= 70:
        priority = "HIGH"
    elif total_score >= 40:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "risk_score": total_score,
        "priority": priority
    }
