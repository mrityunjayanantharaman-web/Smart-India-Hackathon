import math
import time
from pathlib import Path

import duckdb
import ee
import h3
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
OUTPUT_CSV = PROJECT_ROOT / "data" / "processed" / "context_features.csv"
PROJECT_ID = "project-59ef4ae8-2ca1-49bd-86f"


def h3_center(cell):
    try:
        return h3.cell_to_latlng(cell)
    except AttributeError:
        return h3.h3_to_geo(cell)


ee.Initialize(project=PROJECT_ID)
print("Earth Engine initialized.")

conn = duckdb.connect(str(DB_PATH))
sites = conn.execute(
    """
    SELECT h3_cell
    FROM persistent_firms_sites
    ORDER BY risk_score DESC
    """
).fetchdf()

if sites.empty:
    raise RuntimeError("No persistent sites found.")

coordinates = sites["h3_cell"].apply(h3_center)
sites["latitude"] = coordinates.apply(lambda value: float(value[0]))
sites["longitude"] = coordinates.apply(lambda value: float(value[1]))
print(f"Persistent sites loaded: {len(sites)}")

print("Querying ESA WorldCover 2021...")
worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
features = []

for index, row in sites.iterrows():
    point = ee.Geometry.Point([row["longitude"], row["latitude"]])
    histogram = worldcover.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=point.buffer(250),
        scale=10,
        maxPixels=100000,
    ).getInfo().get("Map", {})
    total_pixels = sum(histogram.values())
    ratios = {
        "built_up_ratio": histogram.get("50", 0) / total_pixels if total_pixels else 0,
        "cropland_ratio": histogram.get("40", 0) / total_pixels if total_pixels else 0,
        "tree_cover_ratio": histogram.get("10", 0) / total_pixels if total_pixels else 0,
        "grassland_ratio": histogram.get("30", 0) / total_pixels if total_pixels else 0,
        "bare_land_ratio": histogram.get("60", 0) / total_pixels if total_pixels else 0,
    }
    features.append({"h3_cell": row["h3_cell"], **ratios})
    print(f"WorldCover {index + 1}/{len(sites)}", end="\r")

print()
context_df = pd.DataFrame(features)
print("WorldCover extraction complete.")

print("Querying OpenStreetMap industrial context...")
overpass_urls = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
osm_session = requests.Session()
osm_session.headers.update({"User-Agent": "AgniNetra/0.1 research pipeline"})


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def fetch_osm_elements_in_bbox(bounds):
    query = f"""
    [out:json][timeout:120];
    (
      nwr[\"industrial\"]({bounds});
      nwr[\"landuse\"=\"industrial\"]({bounds});
      nwr[\"man_made\"=\"works\"]({bounds});
      nwr[\"power\"=\"plant\"]({bounds});
    );
    out center;
    """
    last_error = None
    for attempt in range(3):
        endpoint = overpass_urls[attempt % len(overpass_urls)]
        try:
            response = osm_session.post(
                endpoint,
                data={"data": query},
                timeout=90,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("elements", [])
        except (requests.RequestException, ValueError) as error:
            last_error = error
            time.sleep(2 ** attempt)

    print(f"\nOSM batch query failed after retries: {last_error}")
    return []


bbox_south = float(sites["latitude"].min())
bbox_north = float(sites["latitude"].max())
bbox_west = float(sites["longitude"].min())
bbox_east = float(sites["longitude"].max())
lat_padding = max(0.05, (bbox_north - bbox_south) * 0.10)
lon_padding = max(0.05, (bbox_east - bbox_west) * 0.10)
search_bounds = (
    f"{max(bbox_south - lat_padding, -90):.6f},{max(bbox_west - lon_padding, -180):.6f},"
    f"{min(bbox_north + lat_padding, 90):.6f},{min(bbox_east + lon_padding, 180):.6f}"
)

osm_elements = fetch_osm_elements_in_bbox(search_bounds)


def osm_point(element):
    if "center" in element:
        center = element["center"]
        return float(center["lat"]), float(center["lon"])
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    return None


all_osm_points = []
for element in osm_elements:
    point = osm_point(element)
    if point is not None:
        all_osm_points.append(point)

osm_counts = []
for _, row in sites.iterrows():
    count = sum(
        1
        for osm_lat, osm_lon in all_osm_points
        if haversine_km(osm_lat, osm_lon, row["latitude"], row["longitude"]) <= 2.0
    )
    osm_counts.append({"h3_cell": row["h3_cell"], "osm_industrial_features": count})

osm_df = pd.DataFrame(osm_counts)
print("OSM extraction complete")

print("Loading power-plant context...")
power_url = "https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv"
try:
    power_df = pd.read_csv(power_url)
    power_df = power_df[power_df["country"].astype(str).str.upper() == "IND"].copy()
    print(f"Indian power plants loaded: {len(power_df)}")
    print("GPPD extraction complete")
except Exception as error:
    print(f"Could not download power database: {error}")
    power_df = pd.DataFrame()


def count_nearby_power_plants(lat, lon, radius_km=10):
    if power_df.empty:
        return 0
    lat_diff = power_df["latitude"] - lat
    lon_diff = (power_df["longitude"] - lon) * 0.95
    distance_km = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111
    return int((distance_km <= radius_km).sum())


power_counts = []
for _, row in sites.iterrows():
    power_counts.append({
        "h3_cell": row["h3_cell"],
        "nearby_power_plants_10km": count_nearby_power_plants(row["latitude"], row["longitude"]),
    })
power_context_df = pd.DataFrame(power_counts)

context_df = context_df.merge(osm_df, on="h3_cell", how="left").merge(power_context_df, on="h3_cell", how="left")
context_df["industrial_context_score"] = (
    context_df["built_up_ratio"] * 0.35
    + context_df["osm_industrial_features"].clip(upper=10) / 10 * 0.40
    + context_df["nearby_power_plants_10km"].clip(upper=5) / 5 * 0.25
)
context_df["wildland_context_score"] = (
    context_df["tree_cover_ratio"] * 0.40
    + context_df["grassland_ratio"] * 0.30
    + context_df["bare_land_ratio"] * 0.10
    + context_df["cropland_ratio"] * 0.20
)

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
context_df.to_csv(OUTPUT_CSV, index=False)
conn.execute("DROP TABLE IF EXISTS context_features")
conn.register("context_df", context_df)
conn.execute("CREATE TABLE context_features AS SELECT * FROM context_df")

print()
print("=" * 60)
print("STEP 21 COMPLETE")
print("=" * 60)
print(f"Sites processed: {len(context_df)}")
print(f"CSV: {OUTPUT_CSV}")
print("DuckDB table: context_features")
print("\nColumns:")
for column in context_df.columns:
    print(f"  - {column}")
print("\n", context_df.head(5).to_string(index=False))
conn.close()
