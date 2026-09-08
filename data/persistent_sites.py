from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def create_persistent_sites():
    conn = duckdb.connect(str(DB_PATH))

    print("================================")
    print("AGNINETRA PERSISTENT SITE ENGINE")
    print("================================")
    print()

    conn.execute("DROP TABLE IF EXISTS persistent_firms_sites")

    conn.execute(
        """
        CREATE TABLE persistent_firms_sites AS
        SELECT
            h3_cell,
            COUNT(*) AS detection_count,
            COUNT(DISTINCT observation_date) AS active_days,
            MIN(observation_date) AS first_detection,
            MAX(observation_date) AS last_detection,
            AVG(frp) AS avg_frp,
            MAX(frp) AS max_frp,
            AVG(brightness_temperature) AS avg_brightness_temperature,
            COUNT(CASE WHEN daynight = 'D' THEN 1 END) AS daytime_detections,
            COUNT(CASE WHEN daynight = 'N' THEN 1 END) AS nighttime_detections
        FROM firms_detections
        GROUP BY h3_cell
        HAVING COUNT(DISTINCT observation_date) >= 2
        """
    )

    conn.execute(
        """
        ALTER TABLE persistent_firms_sites
        ADD COLUMN persistence_score DOUBLE
        """
    )

    conn.execute(
        """
        UPDATE persistent_firms_sites
        SET persistence_score =
            LEAST(active_days / 5.0, 1.0) * 0.6
            + LEAST(detection_count / 10.0, 1.0) * 0.4
        """
    )

    total_sites = conn.execute(
        "SELECT COUNT(*) FROM persistent_firms_sites"
    ).fetchone()[0]
    highly_persistent = conn.execute(
        """
        SELECT COUNT(*)
        FROM persistent_firms_sites
        WHERE persistence_score >= 0.70
        """
    ).fetchone()[0]

    print(f"Total persistent sites : {total_sites:,}")
    print(f"High-persistence sites : {highly_persistent:,}")
    print()
    print("TOP PERSISTENT SITES")
    print("--------------------------------")

    rows = conn.execute(
        """
        SELECT
            h3_cell,
            detection_count,
            active_days,
            ROUND(avg_frp, 2),
            ROUND(max_frp, 2),
            ROUND(persistence_score, 3)
        FROM persistent_firms_sites
        ORDER BY persistence_score DESC
        LIMIT 10
        """
    ).fetchall()

    for row in rows:
        print(
            f"H3: {row[0]} | "
            f"Detections: {row[1]} | "
            f"Active days: {row[2]} | "
            f"Avg FRP: {row[3]} MW | "
            f"Max FRP: {row[4]} MW | "
            f"Persistence: {row[5]}"
        )

    print()
    print("PERSISTENT SITE ANALYSIS COMPLETE")
    conn.close()


if __name__ == "__main__":
    create_persistent_sites()
