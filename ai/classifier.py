def classify_thermal_source(
    detection_count,
    active_days,
    avg_frp,
    max_frp,
    daytime_detections,
    nighttime_detections
):
    """Prototype multi-source thermal classification."""
    industrial = 0.0
    wildfire = 0.0
    agricultural = 0.0
    flare = 0.0
    other = 0.20

    total_daynight = daytime_detections + nighttime_detections

    if active_days >= 4:
        industrial += 0.30
    if detection_count >= 6:
        industrial += 0.20
    if avg_frp >= 5:
        industrial += 0.15
    if total_daynight > 0 and nighttime_detections / total_daynight >= 0.30:
        industrial += 0.15

    if max_frp >= 80:
        wildfire += 0.45
    if avg_frp >= 20:
        wildfire += 0.20
    if active_days <= 3:
        wildfire += 0.15

    if active_days <= 5:
        agricultural += 0.25
    if avg_frp < 20:
        agricultural += 0.20
    if daytime_detections > nighttime_detections:
        agricultural += 0.15

    if avg_frp >= 40:
        flare += 0.35
    if max_frp >= 80:
        flare += 0.25
    if active_days >= 4:
        flare += 0.15

    scores = {
        "Industrial": round(industrial, 3),
        "Wildfire": round(wildfire, 3),
        "Agricultural": round(agricultural, 3),
        "Flare": round(flare, 3),
        "Other": round(other, 3)
    }

    classification = max(scores, key=scores.get)
    return {
        "classification": classification,
        "confidence": round(scores[classification], 3),
        "scores": scores
    }