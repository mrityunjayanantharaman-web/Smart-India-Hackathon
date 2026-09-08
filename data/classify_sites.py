from pathlib import Path
import sys

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai.classifier import classify_thermal_source


DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def classify_sites():
    conn = duckdb.connect(str(DB_PATH))

    print("================================")
    print("AGNINETRA SOURCE CLASSIFIER")
    print("================================")
    print()

    columns = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'persistent_firms_sites'
        """
    ).fetchall()
    existing_columns = {row[0] for row in columns}

    for column_name, column_type in (
        ("classification", "VARCHAR"),
        ("classification_confidence", "DOUBLE"),
        ("source_scores", "VARCHAR"),
    ):
        if column_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE persistent_firms_sites ADD COLUMN {column_name} {column_type}"
            )

    rows = conn.execute(
        """
        SELECT h3_cell, detection_count, active_days, avg_frp, max_frp,
            daytime_detections, nighttime_detections
        FROM persistent_firms_sites
        """
    ).fetchall()

    print(f"Sites to classify: {len(rows):,}")
    print()
    classification_counts = {}

    for row in rows:
        result = classify_thermal_source(
            detection_count=row[1],
            active_days=row[2],
            avg_frp=row[3],
            max_frp=row[4],
            daytime_detections=row[5],
            nighttime_detections=row[6],
        )
        conn.execute(
            """
            UPDATE persistent_firms_sites
            SET classification = ?, classification_confidence = ?, source_scores = ?
            WHERE h3_cell = ?
            """,
            [
                result["classification"],
                result["confidence"],
                str(result["scores"]),
                row[0],
            ],
        )
        classification = result["classification"]
        classification_counts[classification] = classification_counts.get(classification, 0) + 1

    print("CLASSIFICATION RESULTS")
    print("--------------------------------")
    for source, count in classification_counts.items():
        print(f"{source:15} : {count:,}")

    print()
    print("TOP CLASSIFIED SITES")
    print("--------------------------------")
    top_sites = conn.execute(
        """
        SELECT h3_cell, classification, ROUND(classification_confidence, 3),
            detection_count, active_days, ROUND(avg_frp, 2),
            ROUND(persistence_score, 3)
        FROM persistent_firms_sites
        ORDER BY classification_confidence DESC
        LIMIT 10
        """
    ).fetchall()
    for site in top_sites:
        print(
            f"H3: {site[0]} | Source: {site[1]} | Confidence: {site[2]} | "
            f"Detections: {site[3]} | Active days: {site[4]} | "
            f"Avg FRP: {site[5]} MW | Persistence: {site[6]}"
        )

    print()
    print("SOURCE CLASSIFICATION COMPLETE")
    conn.close()


if __name__ == "__main__":
    classify_sites()
