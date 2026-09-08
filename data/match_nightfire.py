from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def main():
    print("=" * 50)
    print("MATCHING NIGHTFIRE WITH PERSISTENT SITES")
    print("=" * 50)
    conn = duckdb.connect(str(DB_PATH))

    for column_name, column_type in (
        ("nightfire_match", "BOOLEAN"),
        ("nightfire_matches", "INTEGER"),
    ):
        try:
            conn.execute(
                f"ALTER TABLE persistent_firms_sites ADD COLUMN {column_name} {column_type}"
            )
        except Exception:
            pass

    conn.execute(
        """
        UPDATE persistent_firms_sites
        SET nightfire_match = FALSE, nightfire_matches = 0
        """
    )
    conn.execute(
        """
        UPDATE persistent_firms_sites AS p
        SET nightfire_match = TRUE, nightfire_matches = n.match_count
        FROM (
            SELECT h3_cell, COUNT(*) AS match_count
            FROM nightfire_sites
            GROUP BY h3_cell
        ) AS n
        WHERE p.h3_cell = n.h3_cell
        """
    )

    total_sites = conn.execute(
        "SELECT COUNT(*) FROM persistent_firms_sites"
    ).fetchone()[0]
    matched_sites = conn.execute(
        """
        SELECT COUNT(*) FROM persistent_firms_sites WHERE nightfire_match = TRUE
        """
    ).fetchone()[0]
    print()
    print(f"Persistent FIRMS sites: {total_sites}")
    print(f"Nightfire-supported sites: {matched_sites}")
    print()
    print("=" * 50)
    print("TOP NIGHTFIRE-SUPPORTED SITES")
    print("=" * 50)
    rows = conn.execute(
        """
        SELECT h3_cell, detection_count, active_days, classification,
            risk_score, nightfire_matches
        FROM persistent_firms_sites
        WHERE nightfire_match = TRUE
        ORDER BY nightfire_matches DESC, risk_score DESC
        LIMIT 20
        """
    ).fetchall()
    for row in rows:
        print(
            f"H3={row[0]} | FIRMS detections={row[1]} | active_days={row[2]} | "
            f"class={row[3]} | risk={row[4]} | nightfire_matches={row[5]}"
        )
    conn.close()
    print()
    print("=" * 50)
    print("NIGHTFIRE MATCHING COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
