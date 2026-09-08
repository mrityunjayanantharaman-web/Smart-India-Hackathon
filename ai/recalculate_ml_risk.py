import duckdb


DB_PATH = "data/processed/agninetra.duckdb"

conn = duckdb.connect(DB_PATH)

sites = conn.execute(
    """
    SELECT
        h3_cell,
        persistence_score,
        detection_count,
        avg_frp,
        max_frp,
                ml_classification,
                ROUND(LEAST(
                        LEAST(persistence_score, 1.0) * 30
                        + LEAST(detection_count / 10.0, 1.0) * 20
                        + LEAST(avg_frp / 50.0, 1.0) * 20
                        + LEAST(max_frp / 100.0, 1.0) * 15
                        + CASE ml_classification
                                WHEN 'Industrial' THEN 15
                                WHEN 'Flare' THEN 15
                                WHEN 'Wildfire' THEN 12
                                WHEN 'Agricultural' THEN 7
                                ELSE 3
                            END,
                        100
                ), 2) AS calculated_risk_score
    FROM persistent_firms_sites
    WHERE ml_classification IS NOT NULL
    """
).fetchall()

print("=" * 60)
print("AGNINETRA ML-ALIGNED RISK RECALCULATION")
print("=" * 60)

updated = 0

for (
    h3_cell,
    persistence_score,
    detection_count,
    avg_frp,
    max_frp,
    classification,
    calculated_risk_score,
) in sites:
    risk_score = float(calculated_risk_score)

    if risk_score >= 70:
        priority = "HIGH"
    elif risk_score >= 40:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    conn.execute(
        """
        UPDATE persistent_firms_sites
        SET risk_score = ?, priority = ?
        WHERE h3_cell = ?
        """,
        [risk_score, priority, h3_cell],
    )
    updated += 1

conn.close()

print()
print(f"Sites updated: {updated}")
print("Risk classification source: ML classification")
print()
print("Risk formula:")
print("  Persistence       30%")
print("  Detection count   20%")
print("  Average FRP       20%")
print("  Peak FRP          15%")
print("  Source class      15%")
print()
print("=" * 60)
print("STATUS: COMPLETE")
print("=" * 60)
