from pathlib import Path

import duckdb
import h3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "viirs_nightfire_india.csv"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def latlon_to_h3(latitude, longitude):
    return h3.latlng_to_cell(latitude, longitude, 8)


def main():
    print("=" * 50)
    print("LOADING NIGHTFIRE INTO DUCKDB")
    print("=" * 50)
    df = pd.read_csv(INPUT_FILE)
    print(f"\nRows: {len(df):,}")
    df["h3_cell"] = df.apply(
        lambda row: latlon_to_h3(row["latitude"], row["longitude"]), axis=1
    )

    conn = duckdb.connect(str(DB_PATH))
    conn.execute("DROP TABLE IF EXISTS nightfire_sites")
    conn.register("nightfire_dataframe", df)
    conn.execute("CREATE TABLE nightfire_sites AS SELECT * FROM nightfire_dataframe")
    count = conn.execute("SELECT COUNT(*) FROM nightfire_sites").fetchone()[0]
    unique_h3 = conn.execute(
        "SELECT COUNT(DISTINCT h3_cell) FROM nightfire_sites"
    ).fetchone()[0]
    conn.close()

    print()
    print("=" * 50)
    print("NIGHTFIRE DATABASE LOAD COMPLETE")
    print("=" * 50)
    print(f"Records: {count:,}")
    print(f"Unique H3 cells: {unique_h3:,}")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
