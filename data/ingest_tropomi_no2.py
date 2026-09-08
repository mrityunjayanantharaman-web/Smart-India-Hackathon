from pathlib import Path

import duckdb
import ee
import h3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "tropomi_no2_sites.csv"

START_DATE = "2026-08-01"
END_DATE = "2026-08-28"
BUFFER_METERS = 5000


def initialize_earth_engine():
    print("=" * 60)
    print("INITIALIZING GOOGLE EARTH ENGINE")
    print("=" * 60)
    try:
        ee.Initialize(project="project-59ef4ae8-2ca1-49bd-86f")
    except Exception:
        print("\nEarth Engine authentication/project is required.")
        print('Run: python -c "import ee; ee.Authenticate()"')
        raise


def h3_center(h3_cell):
    try:
        return h3.cell_to_latlng(h3_cell)
    except AttributeError:
        return h3.h3_to_geo(h3_cell)


def load_persistent_sites():
    conn = duckdb.connect(str(DB_PATH))
    df = conn.execute(
        """
        SELECT h3_cell, detection_count, active_days, persistence_score,
            classification, risk_score
        FROM persistent_firms_sites
        """
    ).df()
    conn.close()
    return df


def build_features(df):
    features = []
    for _, row in df.iterrows():
        lat, lon = h3_center(row["h3_cell"])
        point = ee.Geometry.Point([lon, lat])
        region = point.buffer(BUFFER_METERS)
        features.append(
            ee.Feature(
                region,
                {"h3_cell": row["h3_cell"], "latitude": lat, "longitude": lon},
            )
        )
    return ee.FeatureCollection(features)


def get_no2_image():
    print()
    print("=" * 60)
    print("LOADING TROPOMI NO2")
    print("=" * 60)
    collection = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
        .filterDate(START_DATE, END_DATE)
        .select("tropospheric_NO2_column_number_density")
    )
    count = collection.size().getInfo()
    print(f"TROPOMI images in period: {count}")
    if count == 0:
        raise RuntimeError("No TROPOMI NO2 images found for the selected period.")
    return collection.mean()


def extract_no2_sites(image, sites):
    print()
    print("=" * 60)
    print("EXTRACTING NO2 AT PERSISTENT SITES")
    print("=" * 60)
    reducer = ee.Reducer.mean().combine(
        reducer2=ee.Reducer.max(), sharedInputs=True
    )
    result = image.reduceRegions(collection=sites, reducer=reducer, scale=1113)
    data = result.getInfo()
    rows = []
    for feature in data["features"]:
        properties = feature["properties"]
        rows.append(
            {
                "h3_cell": properties.get("h3_cell"),
                "latitude": properties.get("latitude"),
                "longitude": properties.get("longitude"),
                "no2_mean": properties.get("mean"),
                "no2_max": properties.get("max"),
            }
        )
    return pd.DataFrame(rows)


def save_to_duckdb(no2_df):
    conn = duckdb.connect(str(DB_PATH))
    conn.execute("DROP TABLE IF EXISTS tropomi_no2_sites")
    conn.register("no2_dataframe", no2_df)
    conn.execute("CREATE TABLE tropomi_no2_sites AS SELECT * FROM no2_dataframe")
    conn.close()


def main():
    initialize_earth_engine()
    sites_df = load_persistent_sites()
    print(f"\nPersistent sites loaded: {len(sites_df)}")
    sites = build_features(sites_df)
    image = get_no2_image()
    no2_df = extract_no2_sites(image, sites)
    print(f"\nNO2 site records: {len(no2_df)}")
    no2_df.to_csv(OUTPUT_FILE, index=False)
    save_to_duckdb(no2_df)
    print()
    print("=" * 60)
    print("TROPOMI NO2 INGESTION COMPLETE")
    print("=" * 60)
    print(f"Saved: {OUTPUT_FILE}")
    print("DuckDB table: tropomi_no2_sites")
    print()
    print(no2_df.head(10).to_string())


if __name__ == "__main__":
    main()
