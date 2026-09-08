import os
from pathlib import Path

import h3
import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

MAP_KEY = os.getenv("FIRMS_MAP_KEY")

if not MAP_KEY:
    raise RuntimeError(
        "FIRMS_MAP_KEY not found. Add it to the AgniNetra/.env file."
    )

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

WEST = 68
SOUTH = 6
EAST = 98
NORTH = 36

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "firms" / "india"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_firms(source="VIIRS_NOAA21_NRT", days=1):
    """Download recent FIRMS data for India."""
    area = f"{WEST},{SOUTH},{EAST},{NORTH}"
    url = f"{BASE_URL}/{MAP_KEY}/{source}/{area}/{days}"

    print("Downloading FIRMS data...")
    print(f"Source: {source}")
    print("Area: India")
    print(f"Days: {days}")

    response = requests.get(url, timeout=120)
    response.raise_for_status()

    output_file = OUTPUT_DIR / f"{source.lower()}_latest.csv"
    output_file.write_bytes(response.content)

    print()
    print("Download complete.")
    print(f"Saved to: {output_file}")
    return output_file


def validate_firms(file_path):
    print()
    print("Validating FIRMS file...")
    df = pd.read_csv(file_path)

    required_columns = [
        "latitude",
        "longitude",
        "acq_date",
        "frp",
        "confidence",
        "daynight",
    ]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing FIRMS columns: {missing}")

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    df = df.dropna(subset=["latitude", "longitude"])
    df = df[
        (df["latitude"] >= SOUTH)
        & (df["latitude"] <= NORTH)
        & (df["longitude"] >= WEST)
        & (df["longitude"] <= EAST)
    ]
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df = df.dropna(subset=["frp"])
    df["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce")
    df = df.dropna(subset=["acq_date"])

    print(f"Valid rows: {len(df):,}")
    return df


def add_h3_cells(df):
    print()
    print("Generating H3 cells...")
    if df.empty:
        df["h3_cell"] = pd.Series(dtype="string", index=df.index)
        return df

    df["h3_cell"] = df.apply(
        lambda row: h3.latlng_to_cell(row["latitude"], row["longitude"], 8),
        axis=1,
    )
    return df


def standardize(df):
    output_columns = [
        "latitude",
        "longitude",
        "h3_cell",
        "acq_date",
        "acq_time",
        "satellite",
        "instrument",
        "confidence",
        "frp",
        "bright_ti4",
        "bright_ti5",
        "daynight",
    ]
    available_columns = [column for column in output_columns if column in df.columns]
    df = df[available_columns]
    return df.rename(
        columns={
            "acq_date": "observation_date",
            "acq_time": "observation_time",
            "bright_ti4": "brightness_temperature",
            "bright_ti5": "background_temperature",
        }
    )


if __name__ == "__main__":
    file_path = download_firms(source="VIIRS_NOAA21_NRT", days=5)
    df = validate_firms(file_path)
    df = add_h3_cells(df)
    df = standardize(df)

    cleaned_file = OUTPUT_DIR / "firms_cleaned.csv"
    df.to_csv(cleaned_file, index=False)

    print()
    print("================================")
    print("FIRMS PIPELINE COMPLETE")
    print("================================")
    print(f"Cleaned rows: {len(df):,}")
    print(f"Saved: {cleaned_file}")