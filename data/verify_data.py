from pathlib import Path

import pandas as pd


FIRMS_FILE = Path(__file__).resolve().parent / "raw" / "firms" / "india" / "firms_cleaned.csv"


def verify_firms():
    print("Verifying FIRMS dataset...")
    print()

    if not FIRMS_FILE.exists():
        raise FileNotFoundError(f"File not found: {FIRMS_FILE}")

    df = pd.read_csv(FIRMS_FILE)
    required_columns = [
        "latitude",
        "longitude",
        "h3_cell",
        "observation_date",
        "frp",
        "daynight",
    ]
    for column in required_columns:
        if column not in df.columns:
            raise ValueError(f"Missing column: {column}")

    if df["latitude"].isna().any():
        raise ValueError("Missing latitude values.")
    if df["longitude"].isna().any():
        raise ValueError("Missing longitude values.")
    if df["frp"].isna().any():
        raise ValueError("Missing FRP values.")

    dates = pd.to_datetime(df["observation_date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("Invalid observation dates.")

    india = df[
        (df["latitude"] >= 6)
        & (df["latitude"] <= 36)
        & (df["longitude"] >= 68)
        & (df["longitude"] <= 98)
    ]
    if len(india) != len(df):
        raise ValueError("Some coordinates are outside India bounds.")

    print("File exists")
    print("Required columns present")
    print("Coordinates valid")
    print("FRP values present")
    print("Dates parse correctly")
    print("Coordinates within India bounds")
    print()
    print(f"Rows verified: {len(df):,}")
    print(f"Unique H3 cells: {df['h3_cell'].nunique():,}")
    print(f"FRP range: {df['frp'].min():.2f} - {df['frp'].max():.2f} MW")
    print(f"Day detections: {(df['daynight'] == 'D').sum():,}")
    print(f"Night detections: {(df['daynight'] == 'N').sum():,}")
    print()
    print("FIRMS verification PASSED")


if __name__ == "__main__":
    verify_firms()