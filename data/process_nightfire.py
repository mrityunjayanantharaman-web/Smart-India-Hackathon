from pathlib import Path
import zipfile

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "viirs_nightfire"
EXTRACT_DIR = INPUT_DIR / "extracted"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_zip():
    zip_files = list(INPUT_DIR.glob("*.zip"))
    if not zip_files:
        raise FileNotFoundError(
            "No VIIRS Nightfire ZIP file found in data/raw/viirs_nightfire/"
        )
    print(f"Found ZIP: {zip_files[0].name}")
    return zip_files[0]


def extract_dataset(zip_file):
    print()
    print("=" * 50)
    print("EXTRACTING VIIRS NIGHTFIRE")
    print("=" * 50)
    with zipfile.ZipFile(zip_file, "r") as archive:
        archive.extractall(EXTRACT_DIR)
    print(f"Extracted to: {EXTRACT_DIR}")


def find_data_files():
    print()
    print("=" * 50)
    print("SEARCHING NIGHTFIRE DATA FILES")
    print("=" * 50)
    files = [
        file for file in EXTRACT_DIR.rglob("*")
        if file.is_file() and file.suffix.lower() in [".csv", ".txt"]
    ]
    if not files:
        raise FileNotFoundError("No CSV/TXT files found inside the Nightfire ZIP.")
    print(f"\nData files found: {len(files)}")
    for file in files:
        print(f" - {file}")
    return files


def inspect_file(file_path):
    print()
    print("=" * 50)
    print(f"INSPECTING: {file_path.name}")
    print("=" * 50)
    try:
        df = pd.read_csv(file_path)
    except Exception:
        try:
            df = pd.read_csv(file_path, sep=None, engine="python")
        except Exception as error:
            print(f"Could not read file: {error}")
            return None
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print("\nColumns:")
    for column in df.columns:
        print(f" - {column}")
    print("\nFirst rows:")
    print(df.head(3).to_string())
    return df


def score_location_file(df):
    columns = {str(column).lower().strip() for column in df.columns}
    score = 0
    if columns.intersection({"latitude", "lat", "y"}):
        score += 3
    if columns.intersection({"longitude", "lon", "lng", "x"}):
        score += 3
    if any("temp" in column for column in columns):
        score += 1
    if any("flare" in column for column in columns):
        score += 1
    if any("volume" in column or "gas" in column for column in columns):
        score += 1
    return score


def main():
    zip_file = find_zip()
    extract_dataset(zip_file)
    data_files = find_data_files()

    print()
    print("=" * 50)
    print("IDENTIFYING FLARE LOCATION FILE")
    print("=" * 50)
    candidates = []
    for file in data_files:
        df = inspect_file(file)
        if df is not None:
            candidates.append({"file": file, "score": score_location_file(df), "rows": len(df)})
    if not candidates:
        raise RuntimeError("No readable Nightfire data files found.")

    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0]
    print()
    print("=" * 50)
    print("BEST LOCATION DATASET")
    print("=" * 50)
    print(f"File: {best['file']}")
    print(f"Score: {best['score']}")
    print(f"Rows: {best['rows']:,}")

    df = pd.read_csv(best["file"], sep=None, engine="python")
    output_file = OUTPUT_DIR / "viirs_nightfire_raw.csv"
    df.to_csv(output_file, index=False)
    print()
    print("=" * 50)
    print("NIGHTFIRE PROCESSING COMPLETE")
    print("=" * 50)
    print(f"Saved: {output_file}")
    print(f"Rows: {len(df):,}")


if __name__ == "__main__":
    main()
