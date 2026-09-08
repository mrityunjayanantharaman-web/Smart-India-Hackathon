from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "viirs_nightfire_raw.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "viirs_nightfire_india.csv"

MIN_LAT, MAX_LAT = 6.0, 36.0
MIN_LON, MAX_LON = 68.0, 98.0


def find_column(columns, candidates):
    normalized = {str(column).lower().strip(): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for column_lower, original in normalized.items():
        if any(candidate in column_lower for candidate in candidates):
            return original
    return None


def main():
    print("=" * 50)
    print("PROCESSING INDIA NIGHTFIRE DATA")
    print("=" * 50)
    df = pd.read_csv(INPUT_FILE)
    print(f"\nInput rows: {len(df):,}")

    lat_col = find_column(df.columns, ["latitude", "lat"])
    lon_col = find_column(df.columns, ["longitude", "lon", "lng"])
    print(f"\nLatitude column: {lat_col}")
    print(f"Longitude column: {lon_col}")
    if lat_col is None or lon_col is None:
        print("\nERROR: Could not identify latitude/longitude columns.")
        for column in df.columns:
            print(f" - {column}")
        raise RuntimeError("Latitude/longitude columns could not be identified.")

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    india = df[
        (df[lat_col] >= MIN_LAT) & (df[lat_col] <= MAX_LAT)
        & (df[lon_col] >= MIN_LON) & (df[lon_col] <= MAX_LON)
    ].copy()
    india["latitude"] = india[lat_col]
    india["longitude"] = india[lon_col]

    print(f"\nValid coordinates: {len(df):,}")
    print(f"India flare records: {len(india):,}")
    india.to_csv(OUTPUT_FILE, index=False)
    print()
    print("=" * 50)
    print("INDIA NIGHTFIRE PROCESSING COMPLETE")
    print("=" * 50)
    print(f"Saved: {OUTPUT_FILE}")
    print(f"India records: {len(india):,}")


if __name__ == "__main__":
    main()
