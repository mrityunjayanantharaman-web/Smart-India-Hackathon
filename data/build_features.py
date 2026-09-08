import duckdb


DB_PATH = "data/processed/agninetra.duckdb"

conn = duckdb.connect(DB_PATH)

print("Building AgniNetra feature table...")

conn.execute("DROP TABLE IF EXISTS thermal_site_features")

conn.execute(
    """
    CREATE TABLE thermal_site_features AS
    WITH firms_stats AS (
        SELECT
            h3_cell,
            STDDEV_SAMP(frp) AS frp_stddev,
            COUNT(*) AS firms_detection_count
        FROM firms_detections
        GROUP BY h3_cell
    )
    SELECT
        p.h3_cell,
        p.detection_count,
        p.active_days,
        p.persistence_score,
        ROUND(p.active_days / 5.0, 4) AS active_day_ratio,
        ROUND(p.detection_count / 5.0, 4) AS detection_frequency,
        p.avg_frp,
        p.max_frp,
        COALESCE(f.frp_stddev, 0) AS frp_stddev,
        CASE
            WHEN p.avg_frp > 0
            THEN ROUND(COALESCE(f.frp_stddev, 0) / p.avg_frp, 4)
            ELSE 0
        END AS frp_coefficient_variation,
        p.avg_brightness_temperature,
        p.daytime_detections,
        p.nighttime_detections,
        CASE
            WHEN (p.daytime_detections + p.nighttime_detections) > 0
            THEN ROUND(
                p.nighttime_detections::DOUBLE /
                (p.daytime_detections + p.nighttime_detections),
                4
            )
            ELSE 0
        END AS night_ratio,
        CAST(p.nightfire_match AS INTEGER) AS nightfire_match,
        p.nightfire_matches,
        COALESCE(p.no2_mean, 0) AS no2_mean,
        COALESCE(p.no2_max, 0) AS no2_max
    FROM persistent_firms_sites p
    LEFT JOIN firms_stats f
        ON p.h3_cell = f.h3_cell
    """
)

count = conn.execute("SELECT COUNT(*) FROM thermal_site_features").fetchone()[0]
print(f"Feature table created: {count} sites")

print("\nFeature columns:")
columns = conn.execute("DESCRIBE thermal_site_features").fetchall()
for column in columns:
    print(f"  {column[0]}")

print("\nSample:")
print(
    conn.execute(
        "SELECT * FROM thermal_site_features LIMIT 5"
    ).fetchdf().to_string(index=False)
)

conn.close()
print("\nFEATURE ENGINEERING COMPLETE")
