import duckdb
from ai.emissions import estimate_emissions


DB_PATH = "data/processed/agninetra.duckdb"

conn = duckdb.connect(DB_PATH)

# Ensure pm25_kg and co2_tonnes columns exist
existing_columns = [
    row[0]
    for row in conn.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'persistent_firms_sites'
    """).fetchall()
]

for col in ["pm25_kg", "co2_tonnes"]:
    if col not in existing_columns:
        conn.execute(f"ALTER TABLE persistent_firms_sites ADD COLUMN {col} DOUBLE")

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
        ), 2) AS calculated_risk_score,
        active_days
    FROM persistent_firms_sites
    WHERE ml_classification IS NOT NULL
    """
).fetchall()

print("=" * 60)
print("AGNINETRA ML-ALIGNED RISK RECALCULATION & EMISSIONS")
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
    active_days,
) in sites:
    risk_score = float(calculated_risk_score)

    if risk_score >= 70:
        priority = "HIGH"
    elif risk_score >= 40:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    emissions = estimate_emissions(avg_frp, active_days, classification)

    conn.execute(
        """
        UPDATE persistent_firms_sites
        SET risk_score = ?, priority = ?, pm25_kg = ?, co2_tonnes = ?
        WHERE h3_cell = ?
        """,
        [risk_score, priority, emissions["pm25_kg"], emissions["co2_tonnes"], h3_cell],
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
