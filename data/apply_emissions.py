"""Apply physically-grounded emissions estimates to persistent thermal sites in DuckDB."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ai.emissions import estimate_emissions

DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def apply_emissions_to_db() -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))

    tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
    if "persistent_firms_sites" not in tables:
        print("[NOTICE] 'persistent_firms_sites' table not found in database.")
        print("Run the data pipeline to generate persistent thermal sites first.")
        conn.close()
        return 0

    # Ensure columns exist using the ALTER TABLE pattern from ai/apply_evidence_model.py
    existing_columns = [
        row[0]
        for row in conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'persistent_firms_sites'
        """).fetchall()
    ]

    new_columns = {
        "pm25_kg": "DOUBLE",
        "co2_tonnes": "DOUBLE",
    }

    for col, dtype in new_columns.items():
        if col not in existing_columns:
            conn.execute(f"ALTER TABLE persistent_firms_sites ADD COLUMN {col} {dtype}")

    # Fetch rows to update
    rows = conn.execute("""
        SELECT
            h3_cell,
            avg_frp,
            active_days,
            ml_classification,
            classification
        FROM persistent_firms_sites
    """).fetchall()

    print("=" * 60)
    print("AGNINETRA EMISSIONS ESTIMATION ENGINE")
    print("=" * 60)
    print(f"Sites to process: {len(rows)}")

    updated = 0
    examples = []

    for h3_cell, avg_frp, active_days, ml_class, legacy_class in rows:
        source_class = ml_class or legacy_class or "Agricultural"
        res = estimate_emissions(avg_frp, active_days, source_class)

        conn.execute(
            """
            UPDATE persistent_firms_sites
            SET pm25_kg = ?, co2_tonnes = ?
            WHERE h3_cell = ?
            """,
            [res["pm25_kg"], res["co2_tonnes"], h3_cell],
        )
        updated += 1
        if len(examples) < 3:
            examples.append((h3_cell, source_class, avg_frp, active_days, res["pm25_kg"], res["co2_tonnes"]))

    conn.close()

    print(f"\nSuccessfully updated {updated} sites with emissions estimates.")
    if examples:
        print("\nSample Calculated Estimates:")
        for h3_cell, cls, frp, days, pm25, co2 in examples:
            print(f"  Site: {h3_cell} ({cls}) | FRP: {frp}MW | Days: {days} -> PM2.5: {pm25} kg, CO2: {co2} tonnes")

    print("\nAssumptions: Wooster 2005 (0.368 kg/MJ), 0.05 duty cycle, Akagi 2011 EFs.")
    print("=" * 60)
    return updated


if __name__ == "__main__":
    apply_emissions_to_db()
