from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIRMS_FILE = PROJECT_ROOT / "data" / "raw" / "firms" / "india" / "firms_cleaned.csv"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"


def load_firms():
    if not FIRMS_FILE.exists():
        raise FileNotFoundError(f"FIRMS file not found: {FIRMS_FILE}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))

    print("================================")
    print("LOADING FIRMS INTO DUCKDB")
    print("================================")
    print()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS firms_detections AS
        SELECT *
        FROM read_csv_auto(?)
        LIMIT 0
        """,
        [str(FIRMS_FILE)],
    )

    conn.execute(
        """
        INSERT INTO firms_detections
        SELECT *
        FROM read_csv_auto(?)
        """,
        [str(FIRMS_FILE)],
    )

    count = conn.execute("SELECT COUNT(*) FROM firms_detections").fetchone()[0]
    h3_count = conn.execute(
        "SELECT COUNT(DISTINCT h3_cell) FROM firms_detections"
    ).fetchone()[0]

    print(f"FIRMS rows loaded : {count:,}")
    print(f"Unique H3 cells   : {h3_count:,}")
    print()
    print("FIRMS DATA LOADED INTO DUCKDB")

    conn.close()


if __name__ == "__main__":
    load_firms()
