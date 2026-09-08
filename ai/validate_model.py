import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
MODEL_PATH = PROJECT_ROOT / "ai" / "agninetra_xgb.json"
RESULTS_PATH = PROJECT_ROOT / "ai" / "model_validation.json"

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
CLASS_NAMES = ["Agricultural", "Industrial"]


def load_training_data() -> tuple[pd.DataFrame, pd.Series]:
    with duckdb.connect(str(DB_PATH)) as connection:
        data = connection.execute(
            """
            SELECT f.*, p.classification
            FROM thermal_site_features AS f
            INNER JOIN persistent_firms_sites AS p
                ON f.h3_cell = p.h3_cell
            """
        ).df()

    missing = [column for column in FEATURES + ["classification"] if column not in data]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data = data[data["classification"].isin(CLASS_NAMES)].copy()
    if len(data) < 20:
        raise ValueError("Not enough labelled sites for validation.")

    labels = (data["classification"] == "Industrial").astype(int)
    features = data[FEATURES].apply(pd.to_numeric, errors="coerce")
    features = features.fillna(features.median()).fillna(0)
    return features, labels


def make_model() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
    )


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Trained model not found: {MODEL_PATH}")

    X, y = load_training_data()
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    predictions = np.empty(len(y), dtype=int)

    for train_indices, test_indices in splitter.split(X, y):
        model = make_model()
        model.fit(X.iloc[train_indices], y.iloc[train_indices])
        predictions[test_indices] = model.predict(X.iloc[test_indices]).astype(int)

    report = classification_report(
        y,
        predictions,
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(y, predictions, labels=[0, 1]).tolist()
    results = {
        "folds": 5,
        "shuffle": True,
        "random_state": 42,
        "samples": int(len(y)),
        "features": FEATURES,
        "accuracy": float(accuracy_score(y, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "confusion_matrix": matrix,
        "classification_report": report,
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("5-FOLD CROSS VALIDATION")
    print()
    print(f"Accuracy:           {results['accuracy']:.3f}")
    print(f"Balanced Accuracy:  {results['balanced_accuracy']:.3f}")
    print(f"Precision:          {results['precision']:.3f}")
    print(f"Recall:             {results['recall']:.3f}")
    print(f"F1 Score:           {results['f1']:.3f}")
    print()
    print("CONFUSION MATRIX")
    print(np.array(matrix))
    print()
    print("CLASSIFICATION REPORT")
    for class_name in CLASS_NAMES:
        metrics = report[class_name]
        print(class_name)
        print(f"  Precision: {metrics['precision']:.3f}")
        print(f"  Recall:    {metrics['recall']:.3f}")
        print(f"  F1:        {metrics['f1-score']:.3f}")
        print(f"  Support:   {int(metrics['support'])}")
    print()
    print(f"Validation results saved to: {RESULTS_PATH}")
    print("Note: this is a provisional validation on 145 rule-labelled sites, not real-world accuracy.")


if __name__ == "__main__":
    main()