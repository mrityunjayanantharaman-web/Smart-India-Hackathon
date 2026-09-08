import duckdb
import pandas as pd
import json
import os

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from xgboost import XGBClassifier

DB_PATH = "data/processed/agninetra.duckdb"
MODEL_PATH = "ai/agninetra_xgb.json"

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
    conn = duckdb.connect(DB_PATH)

    df = conn.execute("""
        SELECT
            f.*,
            p.classification
        FROM thermal_site_features AS f
        INNER JOIN persistent_firms_sites AS p
            ON f.h3_cell = p.h3_cell
    """).df()

    conn.close()

    print(f"Loaded feature rows: {len(df)}")

    # Check required columns
    missing = [col for col in FEATURES if col not in df.columns]

    if missing:
        print("\nMissing feature columns:")
        for col in missing:
            print(f"  - {col}")

        print("\nAvailable columns:")
        for col in df.columns:
            print(f"  - {col}")

        raise SystemExit(1)

    # Only use the two currently available provisional classes
    df = df[
        df["classification"].isin(
            ["Industrial", "Agricultural"]
        )
    ].copy()

    if len(df) < 20:
        raise SystemExit("Not enough labelled sites for training.")

    # Convert labels
    df["target"] = (
        df["classification"] == "Industrial"
    ).astype(int)

    X = df[FEATURES].copy()
    y = df["target"]

    # Clean numeric values
    X = X.apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median()).fillna(0)

    print("\nClass distribution:")
    print(df["classification"].value_counts())

    # Stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y
    )

    model = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print("\n==============================")
    print("AGNINETRA XGBOOST MODEL")
    print("==============================")
    print(f"Training samples : {len(X_train)}")
    print(f"Testing samples  : {len(X_test)}")
    print(f"Accuracy         : {accuracy:.3f}")

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            target_names=["Agricultural", "Industrial"],
            zero_division=0
        )
    )

    # Feature importance
    importance = pd.DataFrame({
        "feature": FEATURES,
        "importance": model.feature_importances_
    }).sort_values(
        "importance",
        ascending=False
    )

    print("\nFeature importance:")
    print(importance.to_string(index=False))

    # Save model
    os.makedirs("ai", exist_ok=True)
    model.save_model(MODEL_PATH)

    print(f"\nModel saved to: {MODEL_PATH}")
    print("\nSTEP 16A COMPLETE")

if __name__ == "__main__":
    main()
