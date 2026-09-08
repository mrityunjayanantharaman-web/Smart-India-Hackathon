import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

# ============================================================
# CONFIG
# ============================================================

DB_PATH = "data/processed/agninetra.duckdb"

MODEL_PATH = "ai/agninetra_xgb_evidence.json"
TRAINING_RESULTS = "ai/evidence_model_training.json"

# ============================================================
# START
# ============================================================

print("=" * 65)
print("AGNI NETRA - STEP 25")
print("APPLY EVIDENCE-BASED XGBOOST MODEL")
print("=" * 65)

# ============================================================
# LOAD MODEL METADATA
# ============================================================

if not Path(MODEL_PATH).exists():
    raise FileNotFoundError(
        f"Model not found: {MODEL_PATH}"
    )

if not Path(TRAINING_RESULTS).exists():
    raise FileNotFoundError(
        f"Training metadata not found: {TRAINING_RESULTS}"
    )

with open(
    TRAINING_RESULTS,
    "r",
    encoding="utf-8"
) as f:
    training_metadata = json.load(f)

feature_columns = training_metadata.get(
    "features",
    []
)

class_names = training_metadata.get(
    "classes",
    []
)

if not feature_columns:
    raise RuntimeError(
        "No feature list found in training metadata."
    )

if not class_names:
    raise RuntimeError(
        "No class names found in training metadata."
    )

print("\nModel:")
print(MODEL_PATH)

print("\nClasses:")
print(class_names)

print("\nExpected features:")
for feature in feature_columns:
    print(" -", feature)

# ============================================================
# LOAD DATABASE
# ============================================================

conn = duckdb.connect(DB_PATH)

tables = [
    row[0]
    for row in conn.execute("SHOW TABLES").fetchall()
]

print("\nDatabase tables:")
for table in tables:
    print(" -", table)

required = [
    "persistent_firms_sites",
    "thermal_site_features",
    "context_features"
]

for table in required:
    if table not in tables:
        raise RuntimeError(
            f"Required table missing: {table}"
        )

# ============================================================
# LOAD DATA
# ============================================================

sites = conn.execute("""
    SELECT *
    FROM persistent_firms_sites
""").fetchdf()

features = conn.execute("""
    SELECT *
    FROM thermal_site_features
""").fetchdf()

context = conn.execute("""
    SELECT *
    FROM context_features
""").fetchdf()

print("\nRows:")
print("Persistent sites:", len(sites))
print("Thermal features:", len(features))
print("Context features:", len(context))

# ============================================================
# MERGE FEATURE SOURCES
# ============================================================

df = features.merge(
    context,
    on="h3_cell",
    how="left",
    suffixes=("", "_context")
)

df = df.merge(
    sites[
        ["h3_cell"]
    ],
    on="h3_cell",
    how="inner"
)

print(
    "\nMerged inference dataset:",
    len(df)
)

# ============================================================
# CHECK ALL MODEL FEATURES
# ============================================================

missing_features = [
    feature
    for feature in feature_columns
    if feature not in df.columns
]

if missing_features:
    print("\nMissing model features:")

    for feature in missing_features:
        print(" -", feature)

    raise RuntimeError(
        "Inference cannot continue because "
        "required model features are missing."
    )

# ============================================================
# BUILD X
# ============================================================

X = df[
    feature_columns
].copy()

X = X.replace(
    [np.inf, -np.inf],
    np.nan
)

# Use the same basic missing-value strategy
# used during training.

for column in X.columns:

    if X[column].isna().all():
        X[column] = 0

    else:
        X[column] = X[column].fillna(
            X[column].median()
        )

X = X.fillna(0)

# ============================================================
# LOAD XGBOOST MODEL
# ============================================================

print("\nLoading evidence-based XGBoost...")

model = XGBClassifier()

model.load_model(
    MODEL_PATH
)

# ============================================================
# PREDICTION
# ============================================================

print(
    "Running inference for",
    len(X),
    "persistent sites..."
)

probabilities = model.predict_proba(X)

predicted_indices = np.argmax(
    probabilities,
    axis=1
)

predicted_labels = [
    class_names[int(index)]
    for index in predicted_indices
]

confidence = probabilities.max(
    axis=1
)

# ============================================================
# BUILD PROBABILITY JSON
# ============================================================

probability_records = []

for row in probabilities:

    record = {}

    for index, class_name in enumerate(
        class_names
    ):
        record[class_name] = round(
            float(row[index]),
            4
        )

    probability_records.append(
        json.dumps(record)
    )

# ============================================================
# RESULT DATAFRAME
# ============================================================

predictions = pd.DataFrame({
    "h3_cell": df["h3_cell"].values,

    "ml_classification": predicted_labels,

    "ml_confidence": np.round(
        confidence,
        4
    ),

    "ml_probabilities": probability_records,

    "ml_model": [
        "agninetra_xgb_evidence"
    ] * len(df)
})

# ============================================================
# PRINT DISTRIBUTION
# ============================================================

print("\n" + "=" * 65)
print("ML PREDICTION DISTRIBUTION")
print("=" * 65)

print(
    predictions[
        "ml_classification"
    ].value_counts()
)

print("\nAverage confidence:")

print(
    round(
        predictions[
            "ml_confidence"
        ].mean(),
        4
    )
)

print("\nMinimum confidence:")

print(
    round(
        predictions[
            "ml_confidence"
        ].min(),
        4
    )
)

print("\nMaximum confidence:")

print(
    round(
        predictions[
            "ml_confidence"
        ].max(),
        4
    )
)

# ============================================================
# TOP PREDICTIONS
# ============================================================

print("\nTop ML predictions:")

top = predictions.sort_values(
    "ml_confidence",
    ascending=False
).head(10)

print(
    top[
        [
            "h3_cell",
            "ml_classification",
            "ml_confidence",
            "ml_probabilities"
        ]
    ].to_string(
        index=False
    )
)

# ============================================================
# CREATE NEW COLUMNS
# ============================================================

existing_columns = [
    row[0]
    for row in conn.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'persistent_firms_sites'
    """).fetchall()
]

new_columns = {
    "ml_classification": "VARCHAR",
    "ml_confidence": "DOUBLE",
    "ml_probabilities": "VARCHAR",
    "ml_model": "VARCHAR"
}

for column, data_type in new_columns.items():

    if column not in existing_columns:

        conn.execute(
            f"""
            ALTER TABLE persistent_firms_sites
            ADD COLUMN {column} {data_type}
            """
        )

# ============================================================
# UPDATE PERSISTENT SITE TABLE
# ============================================================

print(
    "\nWriting predictions to persistent_firms_sites..."
)

for _, row in predictions.iterrows():

    conn.execute(
        """
        UPDATE persistent_firms_sites
        SET
            ml_classification = ?,
            ml_confidence = ?,
            ml_probabilities = ?,
            ml_model = ?
        WHERE h3_cell = ?
        """,
        [
            row["ml_classification"],
            float(row["ml_confidence"]),
            row["ml_probabilities"],
            row["ml_model"],
            row["h3_cell"]
        ]
    )

# ============================================================
# SAVE PREDICTION TABLE
# ============================================================

conn.execute("""
    DROP TABLE IF EXISTS ml_predictions
""")

conn.register(
    "prediction_df",
    predictions
)

conn.execute("""
    CREATE TABLE ml_predictions AS
    SELECT *
    FROM prediction_df
""")

# ============================================================
# SAVE CSV
# ============================================================

output_csv = (
    "data/processed/"
    "ml_predictions.csv"
)

predictions.to_csv(
    output_csv,
    index=False
)

# ============================================================
# VERIFY
# ============================================================

verification = conn.execute("""
    SELECT
        COUNT(*) AS total,
        COUNT(ml_classification) AS classified,
        COUNT(ml_confidence) AS confidence_available
    FROM persistent_firms_sites
""").fetchone()

print("\nVerification:")
print(
    "Persistent sites:",
    verification[0]
)

print(
    "ML classifications:",
    verification[1]
)

print(
    "ML confidence values:",
    verification[2]
)

# ============================================================
# CLOSE
# ============================================================

conn.close()

print("\nPrediction CSV:")
print(output_csv)

print("\n" + "=" * 65)
print("STEP 25 COMPLETE")
print("=" * 65)
print(
    "Old heuristic classification was preserved."
)
print(
    "New ML predictions were added separately."
)
