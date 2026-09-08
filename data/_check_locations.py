import duckdb

conn = duckdb.connect("data/processed/agninetra.duckdb")
total = conn.execute("SELECT COUNT(*) FROM persistent_firms_sites").fetchone()[0]
named = conn.execute(
    """
    SELECT COUNT(*)
    FROM persistent_firms_sites
    WHERE location_name IS NOT NULL AND TRIM(location_name) <> ''
    """
).fetchone()[0]
samples = conn.execute(
    """
    SELECT h3_cell, location_name
    FROM persistent_firms_sites
    WHERE location_name IS NOT NULL AND TRIM(location_name) <> ''
    LIMIT 10
    """
).fetchall()
print("total", total)
print("named", named)
for row in samples:
    print(row)
