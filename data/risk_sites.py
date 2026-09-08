from pathlib import Path
import sys

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai.risk import calculate_risk_score


DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def calculate_site_risks():
    conn = duckdb.connect(str(DB_PATH))

    print("================================")
    print("AGNINETRA RISK ENGINE")
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

    if "risk_score" not in existing_columns:
        conn.execute(
            "ALTER TABLE persistent_firms_sites ADD COLUMN risk_score DOUBLE"
        )

    if "priority" not in existing_columns:
        conn.execute(
            "ALTER TABLE persistent_firms_sites ADD COLUMN priority VARCHAR"
        )

    rows = conn.execute(
        """
        SELECT h3_cell, persistence_score, detection_count,
            avg_frp, max_frp, classification
        FROM persistent_firms_sites
        """
    ).fetchall()

    print(f"Sites to score: {len(rows):,}")
    print()
    priority_counts = {}

    for row in rows:
        result = calculate_risk_score(
            persistence_score=row[1],
            detection_count=row[2],
            avg_frp=row[3],
            max_frp=row[4],
            classification=row[5]
        )
        conn.execute(
            """
            UPDATE persistent_firms_sites
            SET risk_score = ?, priority = ?
            WHERE h3_cell = ?
            """,
            [result["risk_score"], result["priority"], row[0]]
        )
        priority = result["priority"]
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    print("RISK PRIORITY RESULTS")
    print("--------------------------------")
    for priority in ["HIGH", "MEDIUM", "LOW"]:
        print(f"{priority:10} : {priority_counts.get(priority, 0):,}")

    print()
    print("TOP 10 HIGH-RISK SITES")
    print("--------------------------------")
    top_sites = conn.execute(
        """
        SELECT h3_cell, classification, ROUND(risk_score, 2), priority,
            detection_count, active_days, ROUND(avg_frp, 2),
            ROUND(persistence_score, 3)
        FROM persistent_firms_sites
        ORDER BY risk_score DESC
        LIMIT 10
        """
    ).fetchall()

    for site in top_sites:
        print(
            f"H3: {site[0]} | Source: {site[1]} | Risk: {site[2]} | "
            f"Priority: {site[3]} | Detections: {site[4]} | "
            f"Active days: {site[5]} | Avg FRP: {site[6]} MW | "
            f"Persistence: {site[7]}"
        )

    print()
    print("RISK ANALYSIS COMPLETE")
    conn.close()


if __name__ == "__main__":
    calculate_site_risks()
