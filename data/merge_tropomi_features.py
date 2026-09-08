from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def add_column_if_missing(conn, column, data_type):
    columns = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'persistent_firms_sites'
        """
    ).fetchall()
    existing_columns = {row[0] for row in columns}
    if column not in existing_columns:
        conn.execute(
            f"ALTER TABLE persistent_firms_sites ADD COLUMN {column} {data_type}"
        )


def main():
    print("=" * 60)
    print("MERGING TROPOMI NO2 FEATURES")
    print("=" * 60)

    conn = duckdb.connect(str(DB_PATH))
    add_column_if_missing(conn, "no2_mean", "DOUBLE")
    add_column_if_missing(conn, "no2_max", "DOUBLE")

    conn.execute(
        """
        UPDATE persistent_firms_sites
        SET no2_mean = NULL, no2_max = NULL
        """
    )
    conn.execute(
        """
        UPDATE persistent_firms_sites AS p
        SET no2_mean = n.no2_mean, no2_max = n.no2_max
        FROM tropomi_no2_sites AS n
        WHERE p.h3_cell = n.h3_cell
        """
    )

    total = conn.execute(
        "SELECT COUNT(*) FROM persistent_firms_sites"
    ).fetchone()[0]
    with_no2 = conn.execute(
        "SELECT COUNT(*) FROM persistent_firms_sites WHERE no2_mean IS NOT NULL"
    ).fetchone()[0]

    print(f"\nPersistent sites: {total}")
    print(f"Sites with NO2 data: {with_no2}")
    print()
    print("=" * 60)
    print("TOP NO2 SITES")
    print("=" * 60)

    rows = conn.execute(
        """
        SELECT h3_cell, classification, risk_score, no2_mean, no2_max
        FROM persistent_firms_sites
        WHERE no2_mean IS NOT NULL
        ORDER BY no2_mean DESC
        LIMIT 10
        """
    ).fetchall()
    for row in rows:
        print(
            f"H3={row[0]} | class={row[1]} | risk={row[2]} | "
            f"NO2_mean={row[3]} | NO2_max={row[4]}"
        )

    conn.close()
    print()
    print("=" * 60)
    print("TROPOMI MERGE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
