import os

import duckdb
import pandas as pd


DB_PATH = "data/processed/agninetra.duckdb"

print("=" * 60)
print("AGNINETRA FINAL SYSTEM VALIDATION")
print("=" * 60)

errors = []
warnings = []

# --------------------------------------------------
# 1. Database
# --------------------------------------------------

if not os.path.exists(DB_PATH):
    errors.append("DuckDB database not found")
    conn = None
else:
    print("\n[1] DATABASE")
    print("OK:", DB_PATH)
    conn = duckdb.connect(DB_PATH)

if conn is not None:
    tables = conn.execute("SHOW TABLES").df()["name"].tolist()

    required_tables = [
        "firms_detections",
        "persistent_firms_sites",
        "nightfire_sites",
        "tropomi_no2_sites",
        "thermal_site_features",
        "context_features",
        "evidence_labels",
        "ml_predictions",
        "shap_explanations",
    ]

    for table in required_tables:
        if table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  [OK] {table}: {count} rows")
        else:
            errors.append(f"Missing table: {table}")

    # --------------------------------------------------
    # 2. Site consistency
    # --------------------------------------------------

    print("\n[2] SITE CONSISTENCY")

    site_count = conn.execute("SELECT COUNT(*) FROM persistent_firms_sites").fetchone()[0]
    ml_count = conn.execute("SELECT COUNT(*) FROM ml_predictions").fetchone()[0]
    shap_count = conn.execute("SELECT COUNT(*) FROM shap_explanations").fetchone()[0]

    print("  Persistent sites:", site_count)
    print("  ML predictions:", ml_count)
    print("  SHAP explanations:", shap_count)

    if ml_count != site_count:
        errors.append(f"ML prediction count mismatch: {ml_count} vs {site_count}")

    if shap_count != site_count:
        errors.append(f"SHAP explanation count mismatch: {shap_count} vs {site_count}")

    # --------------------------------------------------
    # 3. ML prediction validity
    # --------------------------------------------------

    print("\n[3] ML PREDICTIONS")

    invalid_confidence = conn.execute(
        """
        SELECT COUNT(*)
        FROM persistent_firms_sites
        WHERE ml_confidence < 0
           OR ml_confidence > 1
           OR ml_confidence IS NULL
        """
    ).fetchone()[0]

    if invalid_confidence:
        errors.append(f"Invalid ML confidence values: {invalid_confidence}")
    else:
        print("  [OK] Confidence values valid")

    classes = conn.execute(
        """
        SELECT ml_classification, COUNT(*) AS sites
        FROM persistent_firms_sites
        GROUP BY ml_classification
        ORDER BY sites DESC
        """
    ).df()

    print("\n  Classification distribution:")
    print(classes.to_string(index=False))

    # --------------------------------------------------
    # 4. Risk validity
    # --------------------------------------------------

    print("\n[4] RISK SCORES")

    invalid_risk = conn.execute(
        """
        SELECT COUNT(*)
        FROM persistent_firms_sites
        WHERE risk_score < 0
           OR risk_score > 100
           OR risk_score IS NULL
        """
    ).fetchone()[0]

    if invalid_risk:
        errors.append(f"Invalid risk scores: {invalid_risk}")
    else:
        print("  [OK] Risk scores within 0-100")

    # --------------------------------------------------
    # 5. FIRMS data quality
    # --------------------------------------------------

    print("\n[5] FIRMS DATA QUALITY")

    firms_count = conn.execute("SELECT COUNT(*) FROM firms_detections").fetchone()[0]
    invalid_coords = conn.execute(
        """
        SELECT COUNT(*)
        FROM firms_detections
        WHERE latitude NOT BETWEEN 6 AND 36
           OR longitude NOT BETWEEN 68 AND 98
        """
    ).fetchone()[0]
    invalid_frp = conn.execute(
        """
        SELECT COUNT(*)
        FROM firms_detections
        WHERE frp IS NULL OR frp < 0
        """
    ).fetchone()[0]

    print("  FIRMS detections:", firms_count)
    print("  Invalid coordinates:", invalid_coords)
    print("  Invalid FRP:", invalid_frp)

    if invalid_coords:
        errors.append(f"Invalid FIRMS coordinates: {invalid_coords}")
    if invalid_frp:
        errors.append(f"Invalid FIRMS FRP values: {invalid_frp}")

    # --------------------------------------------------
    # 6. Context data
    # --------------------------------------------------

    print("\n[6] CONTEXT DATA")

    context = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(built_up_ratio) AS built_up,
            COUNT(cropland_ratio) AS cropland,
            COUNT(nearby_power_plants_10km) AS power_plants,
            COUNT(industrial_context_score) AS industrial_context,
            COUNT(wildland_context_score) AS wildland_context
        FROM context_features
        """
    ).df()

    print(context.to_string(index=False))

    tropomi = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(no2_mean) AS no2,
            COUNT(no2_max) AS no2_max
        FROM tropomi_no2_sites
        """
    ).df()

    print("\n  TROPOMI coverage:")
    print(tropomi.to_string(index=False))

    osm_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM context_features
        WHERE osm_industrial_features > 0
        """
    ).fetchone()[0]

    if osm_count == 0:
        warnings.append("OSM industrial evidence is currently unavailable/zero")

    # --------------------------------------------------
    # 7. Evidence labels
    # --------------------------------------------------

    print("\n[7] EVIDENCE LABELS")

    labels = conn.execute(
        """
        SELECT evidence_label, COUNT(*) AS sites
        FROM evidence_labels
        GROUP BY evidence_label
        ORDER BY sites DESC
        """
    ).df()

    print(labels.to_string(index=False))

    labeled = conn.execute(
        """
        SELECT COUNT(*)
        FROM evidence_labels
        WHERE evidence_label != 'Unknown'
        """
    ).fetchone()[0]

    print("\n  Usable evidence-labeled sites:", labeled)

    if labeled < 50:
        warnings.append("Evidence-labeled sample is small; model metrics are prototype-level")

    # --------------------------------------------------
    # 8. SHAP validation
    # --------------------------------------------------

    print("\n[8] SHAP EXPLANATIONS")

    shap_rows = conn.execute("SELECT explanations FROM shap_explanations").fetchall()
    empty_shap = sum(
        value is None or value == "[]" or value == []
        for (value,) in shap_rows
    )

    if empty_shap:
        errors.append(f"Sites without SHAP explanations: {empty_shap}")
    else:
        print("  [OK] All sites have explanations")

    # --------------------------------------------------
    # 9. Model files
    # --------------------------------------------------

    print("\n[9] MODEL ARTIFACTS")

    model_files = [
        "ai/agninetra_xgb_evidence.json",
        "ai/evidence_model_training.json",
        "ai/shap_importance.json",
    ]

    for path in model_files:
        if os.path.exists(path):
            print("  [OK]", path)
        else:
            warnings.append(f"Missing model artifact: {path}")

    conn.close()

print("\n" + "=" * 60)
print("FINAL VALIDATION SUMMARY")
print("=" * 60)

if errors:
    print("\nERRORS:")
    for error in errors:
        print("  [ERROR]", error)
else:
    print("\n[OK] NO CRITICAL ERRORS")

if warnings:
    print("\nWARNINGS:")
    for warning in warnings:
        print("  [WARNING]", warning)
else:
    print("\n[OK] NO WARNINGS")

print("\n" + "=" * 60)
print("STATUS:", "FAIL" if errors else "PASS")
print("=" * 60)
