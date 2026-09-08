"""Populate cached location_name values for persistent thermal sites."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb
import h3
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import ensure_location_name_column

DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "AgniNetra-SIH/1.0 (thermal-intelligence-platform)"


def format_location_name(address: dict, display_name: str) -> str:
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("suburb")
        or address.get("county")
        or address.get("state_district")
    )
    state = address.get("state")
    parts = [part for part in (city, state) if part]
    if parts:
        return ", ".join(parts)

    if display_name:
        return ", ".join(part.strip() for part in display_name.split(",")[:2] if part.strip())

    return "Unknown location"


def reverse_geocode(latitude: float, longitude: float) -> str:
    response = requests.get(
        NOMINATIM_URL,
        params={
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "zoom": 10,
            "addressdetails": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    return format_location_name(payload.get("address", {}), payload.get("display_name", ""))


def populate_location_names() -> None:
    conn = duckdb.connect(str(DB_PATH))
    ensure_location_name_column(conn)

    rows = conn.execute(
        """
        SELECT h3_cell, location_name
        FROM persistent_firms_sites
        WHERE location_name IS NULL OR TRIM(location_name) = ''
        ORDER BY h3_cell
        """
    ).fetchall()

    print("================================")
    print("AGNINETRA LOCATION NAME CACHE")
    print("================================")
    print(f"Sites to geocode: {len(rows):,}")
    print()

    for index, (h3_cell, _) in enumerate(rows, start=1):
        latitude, longitude = h3.cell_to_latlng(h3_cell)
        try:
            location_name = reverse_geocode(latitude, longitude)
        except requests.RequestException as error:
            print(f"[WARN] {h3_cell}: {error}")
            location_name = "Unknown location"

        conn.execute(
            """
            UPDATE persistent_firms_sites
            SET location_name = ?
            WHERE h3_cell = ?
            """,
            [location_name, h3_cell],
        )
        print(f"[{index}/{len(rows)}] {h3_cell} -> {location_name}".encode("ascii", "replace").decode("ascii"))
        time.sleep(1.1)

    conn.close()
    print()
    print("Location names cached in DuckDB.")


if __name__ == "__main__":
    populate_location_names()
