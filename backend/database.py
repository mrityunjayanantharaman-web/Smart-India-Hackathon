from pathlib import Path

import duckdb


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "agninetra.duckdb"


def get_connection():
    return duckdb.connect(str(DATABASE_PATH))


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DATABASE_PATH)) as connection:
        connection.execute("CREATE SEQUENCE IF NOT EXISTS thermal_event_id_seq START 1")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS thermal_events (
                event_id INTEGER PRIMARY KEY DEFAULT nextval('thermal_event_id_seq'),
                latitude DOUBLE NOT NULL,
                longitude DOUBLE NOT NULL,
                frp DOUBLE NOT NULL,
                brightness_temperature DOUBLE NOT NULL,
                confidence DOUBLE NOT NULL,
                source VARCHAR NOT NULL,
                h3_cell VARCHAR NOT NULL,
                observation_time TIMESTAMP NOT NULL DEFAULT current_timestamp,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
            """
        )
        columns = connection.execute("PRAGMA table_info('thermal_events')").fetchall()
        if not any(column[1] == "observation_time" for column in columns):
            connection.execute("ALTER TABLE thermal_events ADD COLUMN observation_time TIMESTAMP")
            connection.execute(
                "UPDATE thermal_events SET observation_time = created_at WHERE observation_time IS NULL"
            )
        if not any(column[1] == "created_at" for column in columns):
            connection.execute("ALTER TABLE thermal_events ADD COLUMN created_at TIMESTAMP")
            connection.execute(
                "UPDATE thermal_events SET created_at = current_timestamp WHERE created_at IS NULL"
            )
        ensure_location_name_column(connection)


def ensure_location_name_column(connection) -> None:
    columns = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'persistent_firms_sites'
        """
    ).fetchall()
    existing_columns = {row[0] for row in columns}
    if existing_columns and "location_name" not in existing_columns:
        connection.execute(
            "ALTER TABLE persistent_firms_sites ADD COLUMN location_name VARCHAR"
        )


def insert_thermal_event(event: dict, h3_cell: str) -> dict:
    with duckdb.connect(str(DATABASE_PATH)) as connection:
        row = connection.execute(
            """
            INSERT INTO thermal_events (
                latitude,
                longitude,
                frp,
                brightness_temperature,
                confidence,
                source,
                h3_cell,
                observation_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING event_id, latitude, longitude, frp,
                brightness_temperature, confidence, source, h3_cell
            """,
            [
                event["latitude"],
                event["longitude"],
                event["frp"],
                event["brightness_temperature"],
                event["confidence"],
                event["source"],
                h3_cell,
                event["observation_time"],
            ],
        ).fetchone()

    return _row_to_dict(row)


def list_thermal_events() -> list[dict]:
    with duckdb.connect(str(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT event_id, latitude, longitude, frp,
                brightness_temperature, confidence, source, h3_cell
            FROM thermal_events
            ORDER BY event_id
            """
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_persistent_sites() -> list[dict]:
    with duckdb.connect(str(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT
                h3_cell,
                COUNT(*) AS event_count,
                COUNT(DISTINCT DATE(observation_time)) AS active_days,
                AVG(frp) AS avg_frp,
                MAX(frp) AS max_frp,
                AVG(brightness_temperature) AS avg_temperature
            FROM thermal_events
            GROUP BY h3_cell
            HAVING COUNT(*) >= 3
            ORDER BY active_days DESC, event_count DESC
            """
        ).fetchall()

    return [
        {
            "h3_cell": row[0],
            "event_count": row[1],
            "active_days": row[2],
            "avg_frp": round(row[3], 2),
            "max_frp": round(row[4], 2),
            "avg_temperature": round(row[5], 2),
        }
        for row in rows
    ]


def get_firms_summary() -> dict:
    with duckdb.connect(str(DATABASE_PATH)) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_detections,
                COUNT(DISTINCT h3_cell) AS unique_sites,
                AVG(frp) AS average_frp,
                MAX(frp) AS maximum_frp,
                MIN(observation_date) AS first_date,
                MAX(observation_date) AS last_date
            FROM firms_detections
            """
        ).fetchone()

    return {
        "dataset": "NASA FIRMS",
        "total_detections": row[0],
        "unique_h3_sites": row[1],
        "average_frp": round(row[2], 2),
        "maximum_frp": round(row[3], 2),
        "first_date": str(row[4]),
        "last_date": str(row[5]),
    }


def _row_to_dict(row: tuple) -> dict:
    return dict(
        zip(
            (
                "event_id",
                "latitude",
                "longitude",
                "frp",
                "brightness_temperature",
                "confidence",
                "source",
                "h3_cell",
            ),
            row,
        )
    )