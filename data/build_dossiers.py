import duckdb
import json
from pathlib import Path
from datetime import datetime

DB_PATH = "data/processed/agninetra.duckdb"
OUTPUT_DIR = Path("data/processed/dossiers")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_value(value):
    """Convert DuckDB/Python values into JSON-safe values."""
    if value is None:
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def build_dossier(row, columns, shap_features):
    data = {
        columns[i]: safe_value(row[i])
        for i in range(len(columns))
    }

    dossier = {
        "report_metadata": {
            "system": "AgniNetra",
            "report_type": "Thermal Source Investigation Dossier",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "version": "1.0"
        },
        "site": {
            "h3_cell": data.get("h3_cell"),
            "first_detection": str(data.get("first_detection")),
            "last_detection": str(data.get("last_detection")),
            "detection_count": data.get("detection_count"),
            "active_days": data.get("active_days")
        },
        "thermal_profile": {
            "average_frp_mw": data.get("avg_frp"),
            "maximum_frp_mw": data.get("max_frp"),
            "average_brightness_temperature_k": data.get("avg_brightness_temperature"),
            "daytime_detections": data.get("daytime_detections"),
            "nighttime_detections": data.get("nighttime_detections")
        },
        "persistence": {
            "persistence_score": data.get("persistence_score")
        },
        "source_classification": {
            "classification": data.get("classification"),
            "model_confidence": data.get("classification_confidence"),
            "source_scores": data.get("source_scores")
        },
        "risk_assessment": {
            "risk_score": data.get("risk_score"),
            "priority": data.get("priority")
        },
        "satellite_evidence": {
            "nightfire_match": data.get("nightfire_match"),
            "nightfire_matches": data.get("nightfire_matches"),
            "tropomi_no2_mean": data.get("no2_mean"),
            "tropomi_no2_max": data.get("no2_max")
        },
        "explainability": {
            "top_model_features": shap_features
        },
        "investigation_note": (
            "AgniNetra identifies this location as a persistent thermal "
            "source based on satellite observations and multi-source "
            "geospatial evidence. Classification and risk scores are "
            "decision-support indicators and should be verified with "
            "ground-level inspection before enforcement action."
        )
    }

    return dossier


def create_markdown(dossier):
    site = dossier["site"]
    thermal = dossier["thermal_profile"]
    classification = dossier["source_classification"]
    risk = dossier["risk_assessment"]
    evidence = dossier["satellite_evidence"]
    explainability = dossier["explainability"]

    lines = [
        "# AgniNetra Investigation Dossier",
        "",
        f"**Generated:** {dossier['report_metadata']['generated_at']}",
        "",
        "## 1. Site Identification",
        "",
        f"- **H3 Cell:** `{site['h3_cell']}`",
        f"- **First Detection:** {site['first_detection']}",
        f"- **Last Detection:** {site['last_detection']}",
        f"- **Total Detections:** {site['detection_count']}",
        f"- **Active Days:** {site['active_days']}",
        "",
        "## 2. Thermal Profile",
        "",
        f"- **Average FRP:** {thermal['average_frp_mw']} MW",
        f"- **Maximum FRP:** {thermal['maximum_frp_mw']} MW",
        f"- **Average Brightness Temperature:** {thermal['average_brightness_temperature_k']} K",
        f"- **Daytime Detections:** {thermal['daytime_detections']}",
        f"- **Nighttime Detections:** {thermal['nighttime_detections']}",
        "",
        "## 3. Persistence",
        "",
        f"- **Persistence Score:** {site['h3_cell'] and dossier['persistence']['persistence_score']}",
        "",
        "## 4. AI Source Classification",
        "",
        f"- **Predicted Source:** {classification['classification']}",
        f"- **Model Confidence:** {classification['model_confidence']}",
        f"- **Source Scores:** {classification['source_scores']}",
        "",
        "## 5. Risk Assessment",
        "",
        f"- **Risk Score:** {risk['risk_score']}/100",
        f"- **Priority:** **{risk['priority']}**",
        "",
        "## 6. Multi-Source Satellite Evidence",
        "",
        f"- **VIIRS Nightfire Match:** {evidence['nightfire_match']}",
        f"- **Nightfire Matches:** {evidence['nightfire_matches']}",
        f"- **TROPOMI NO2 Mean:** {evidence['tropomi_no2_mean']}",
        f"- **TROPOMI NO2 Maximum:** {evidence['tropomi_no2_max']}",
        "",
        "## 7. Model Explainability",
        "",
        "Top features influencing the current model:",
        ""
    ]

    for feature in explainability["top_model_features"]:
        lines.append(
            f"- **{feature['feature']}** — "
            f"mean |SHAP| = {feature['mean_abs_shap']:.6f}"
        )

    lines.extend([
        "",
        "## 8. Investigation Guidance",
        "",
        dossier["investigation_note"],
        "",
        "---",
        "",
        "**AgniNetra — From satellite fire dots to real-world action.**"
    ])

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("AGNINETRA INVESTIGATION DOSSIER BUILDER")
    print("=" * 60)

    conn = duckdb.connect(DB_PATH)
    shap_path = Path("ai/shap_importance.json")

    if shap_path.exists():
        with open(shap_path, "r", encoding="utf-8") as f:
            shap_data = json.load(f)

        if isinstance(shap_data, list):
            shap_items = shap_data
        elif isinstance(shap_data, dict):
            shap_items = (
                shap_data.get("features")
                or shap_data.get("importance")
                or shap_data.get("top_features")
                or []
            )
        else:
            shap_items = []
    else:
        shap_items = []

    shap_features = []
    for item in shap_items[:10]:
        if isinstance(item, dict):
            feature = item.get("feature") or item.get("name") or item.get("column")
            value = item.get("mean_abs_shap") or item.get("importance") or item.get("value") or 0
            if feature:
                shap_features.append({
                    "feature": feature,
                    "mean_abs_shap": float(value)
                })

    result = conn.execute(
        "SELECT * FROM persistent_firms_sites ORDER BY risk_score DESC"
    )
    rows = result.fetchall()
    columns = [desc[0] for desc in result.description]

    print(f"\nSites found: {len(rows)}")
    print(f"SHAP features loaded: {len(shap_features)}")

    summary = []
    for row in rows:
        dossier = build_dossier(row, columns, shap_features)
        h3_cell = dossier["site"]["h3_cell"]
        if not h3_cell:
            continue

        json_path = OUTPUT_DIR / f"{h3_cell}.json"
        md_path = OUTPUT_DIR / f"{h3_cell}.md"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dossier, f, indent=2, ensure_ascii=False, default=str)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(create_markdown(dossier))

        summary.append({
            "h3_cell": h3_cell,
            "classification": dossier["source_classification"]["classification"],
            "confidence": dossier["source_classification"]["model_confidence"],
            "risk_score": dossier["risk_assessment"]["risk_score"],
            "priority": dossier["risk_assessment"]["priority"]
        })

    conn.close()

    index_path = OUTPUT_DIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total_dossiers": len(summary),
            "dossiers": summary
        }, f, indent=2)

    print("\n" + "=" * 60)
    print("DOSSIER GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nDossiers created: {len(summary)}")
    print(f"Output directory: {OUTPUT_DIR}")

    if summary:
        print("\nTop 5 investigation priorities:")
        for item in summary[:5]:
            print(
                f"  {item['h3_cell']} | "
                f"{item['classification']} | "
                f"Risk {item['risk_score']} | "
                f"{item['priority']}"
            )

    print("\nCreated:")
    print("  - Individual JSON investigation dossiers")
    print("  - Individual Markdown reports")
    print("  - index.json master dossier index")


if __name__ == "__main__":
    main()
