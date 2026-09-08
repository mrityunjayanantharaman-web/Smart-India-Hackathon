import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import shap
import xgboost as xgb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
MODEL_PATH = PROJECT_ROOT / "ai" / "agninetra_xgb_evidence.json"
META_PATH = PROJECT_ROOT / "ai" / "evidence_model_training.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "shap_explanations.json"


def main():
    with duckdb.connect(str(DB_PATH)) as conn:
        features = conn.execute("SELECT * FROM thermal_site_features").df()
        context = conn.execute("SELECT * FROM context_features").df()
        sites = conn.execute("SELECT * FROM persistent_firms_sites").df()

    df = (
        sites
        .merge(features, on="h3_cell", how="left", suffixes=("", "_feature"))
        .merge(context, on="h3_cell", how="left", suffixes=("", "_context"))
    )

    with META_PATH.open("r", encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)

    feature_columns = metadata.get("feature_columns", metadata.get("features", []))
    class_names = metadata.get("classes", [])
    if not feature_columns:
        raise RuntimeError("No model feature list found in training metadata.")

    missing_features = [feature for feature in feature_columns if feature not in df.columns]
    if missing_features:
        raise RuntimeError(f"Missing model features: {', '.join(missing_features)}")

    X = df[feature_columns].copy()
    for column in X.columns:
        X[column] = pd.to_numeric(X[column], errors="coerce")

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_PATH))

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    if isinstance(shap_values, list):
        shap_array = np.stack(shap_values, axis=0)
    else:
        shap_array = np.asarray(shap_values)

    classes = list(model.classes_)
    results = []

    for index, h3_cell in enumerate(df["h3_cell"]):
        prediction = model.predict(X.iloc[[index]])[0]
        class_index = classes.index(prediction)
        prediction_label = (
            class_names[class_index]
            if class_index < len(class_names)
            else str(prediction)
        )
        if shap_array.ndim == 3:
            if shap_array.shape[0] == len(X):
                values = shap_array[index, :, class_index]
            else:
                values = shap_array[class_index, index, :]
        else:
            values = shap_array[index, :]

        ranked = sorted(
            zip(feature_columns, values),
            key=lambda item: abs(float(item[1])),
            reverse=True,
        )[:8]

        explanation = [
            {
                "feature": feature,
                "shap_value": round(float(value), 6),
                "direction": "supports" if value > 0 else "opposes",
            }
            for feature, value in ranked
        ]

        results.append(
            {
                "h3_cell": h3_cell,
                "prediction": prediction_label,
                "explanations": explanation,
            }
        )

    output = pd.DataFrame(results)
    output.to_json(OUTPUT_PATH, orient="records", indent=2)

    with duckdb.connect(str(DB_PATH)) as conn:
        conn.execute("DROP TABLE IF EXISTS shap_explanations")
        conn.register("shap_df", output)
        conn.execute("CREATE TABLE shap_explanations AS SELECT * FROM shap_df")

    print("======================================")
    print("SHAP EXPLANATION COMPLETE")
    print("======================================")
    print(f"Sites explained: {len(output)}")
    print(f"Output: {OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix()}")
    print("DuckDB table: shap_explanations")
    print("======================================")


if __name__ == "__main__":
    main()
