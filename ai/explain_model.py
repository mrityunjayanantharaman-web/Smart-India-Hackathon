import json
from pathlib import Path

import duckdb
import pandas as pd
import shap
import xgboost as xgb
from matplotlib import pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
MODEL_PATH = PROJECT_ROOT / "ai" / "agninetra_xgb.json"
IMPORTANCE_PATH = PROJECT_ROOT / "ai" / "shap_importance.json"
SUMMARY_PATH = PROJECT_ROOT / "ai" / "shap_summary.png"

FEATURES = [
    "persistence_score",
    "active_days",
    "detection_count",
    "avg_frp",
    "max_frp",
    "frp_stddev",
    "frp_coefficient_variation",
    "avg_brightness_temperature",
    "night_ratio",
    "nightfire_match",
    "nightfire_matches",
    "no2_mean",
    "no2_max",
]


def main():
    with duckdb.connect(str(DB_PATH)) as connection:
        data = connection.execute(
            f"SELECT {', '.join(FEATURES)} FROM thermal_site_features"
        ).df()

    X = data.apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median()).fillna(0)
    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_PATH))
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    values = shap_values[1] if isinstance(shap_values, list) else shap_values
    mean_absolute = abs(values).mean(axis=0)
    importance = sorted(
        [
            {"feature": feature, "mean_abs_shap": float(score)}
            for feature, score in zip(FEATURES, mean_absolute)
        ],
        key=lambda item: item["mean_abs_shap"],
        reverse=True,
    )
    IMPORTANCE_PATH.write_text(json.dumps(importance, indent=2), encoding="utf-8")
    shap.summary_plot(values, X, show=False, max_display=10)
    plt.tight_layout()
    plt.savefig(SUMMARY_PATH, dpi=160, bbox_inches="tight")
    plt.close()
    print("Top SHAP features:")
    for index, item in enumerate(importance[:10], start=1):
        print(f"{index}. {item['feature']}: {item['mean_abs_shap']:.6f}")
    print(f"Saved: {IMPORTANCE_PATH}")
    print(f"Saved: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()