import json
from pathlib import Path

import duckdb
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from xgboost import XGBClassifier

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

DB_PATH = "data/processed/agninetra.duckdb"
MODEL_PATH = "ai/agninetra_xgb_evidence.json"
RESULTS_PATH = "ai/evidence_model_training.json"

TEST_SIZE = 0.25
RANDOM_STATE = 42

# --------------------------------------------------
# LOAD DATABASE
# --------------------------------------------------

print("=" * 60)
print("AGNI NETRA - STEP 23")
print("Evidence-Based XGBoost Training")
print("=" * 60)

conn = duckdb.connect(DB_PATH)

tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]

print("\nAvailable tables:")
for table in tables:
    print(" -", table)

required_tables = [
    "thermal_site_features",
    "context_features",
    "evidence_labels",
]

for table in required_tables:
    if table not in tables:
        raise RuntimeError(f"Required table missing: {table}")

# --------------------------------------------------
# INSPECT EVIDENCE LABELS
# --------------------------------------------------

label_columns = (
    conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'evidence_labels'
        ORDER BY ordinal_position
        """
    )
    .fetchdf()["column_name"]
    .tolist()
)

print("\nEvidence label columns:")
print(label_columns)

if "h3_cell" not in label_columns:
    raise RuntimeError("evidence_labels is missing h3_cell")

if "evidence_label" not in label_columns:
    raise RuntimeError("evidence_labels is missing evidence_label")

# --------------------------------------------------
# LOAD FEATURES + LABELS
# --------------------------------------------------

features = conn.execute("SELECT * FROM thermal_site_features").fetchdf()
context = conn.execute("SELECT * FROM context_features").fetchdf()
labels = conn.execute("SELECT * FROM evidence_labels").fetchdf()

conn.close()

print("\nRows:")
print("thermal_site_features:", len(features))
print("context_features:", len(context))
print("evidence_labels:", len(labels))

# --------------------------------------------------
# MERGE DATA
# --------------------------------------------------

df = features.merge(
    context,
    on="h3_cell",
    how="left",
    suffixes=("", "_context"),
)

df = df.merge(
    labels[["h3_cell", "evidence_label", "evidence_confidence"]],
    on="h3_cell",
    how="inner",
)

print("\nMerged dataset:", len(df))

# --------------------------------------------------
# LABEL DISTRIBUTION
# --------------------------------------------------

print("\nOriginal evidence-label distribution:")
print(df["evidence_label"].value_counts(dropna=False))

# --------------------------------------------------
# REMOVE UNKNOWN / INVALID LABELS
# --------------------------------------------------

unknown_values = {"Unknown", "UNKNOWN", "unknown", "", "None", "nan", None}

before = len(df)

df = df[
    df["evidence_label"].notna() & ~df["evidence_label"].isin(unknown_values)
].copy()

excluded = before - len(df)

print("\nExcluded Unknown/unusable labels:", excluded)
print("Usable labeled sites:", len(df))

if len(df) < 10:
    raise RuntimeError("Too few labeled sites for model training.")

# --------------------------------------------------
# FEATURE SELECTION
# --------------------------------------------------

EXCLUDED_FEATURES = {
    "h3_cell",
    "latitude",
    "longitude",
    "classification",
    "classification_confidence",
    "source_scores",
    "risk_score",
    "priority",
    "evidence_label",
    "evidence_confidence",
    "evidence_score",
    "industrial_evidence_score",
    "agricultural_evidence_score",
    "wildfire_evidence_score",
    "evidence_reasons",
    "osm_industrial_features",
}

numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
feature_columns = [
    col for col in numeric_columns if col not in EXCLUDED_FEATURES
]

if not feature_columns:
    raise RuntimeError("No usable numeric features were found.")

print("\nFeatures used for training:")
for feature in feature_columns:
    print(" -", feature)

print("\nTotal features:", len(feature_columns))

# --------------------------------------------------
# CLEAN FEATURES
# --------------------------------------------------

X = df[feature_columns].copy()
X = X.replace([np.inf, -np.inf], np.nan)
X = X.fillna(X.median(numeric_only=True))
X = X.fillna(0)

y = df["evidence_label"].astype(str)

# --------------------------------------------------
# REMOVE CLASSES THAT CANNOT BE VALIDATED
# --------------------------------------------------

class_counts = y.value_counts()
print("\nClass counts:")
print(class_counts)

valid_classes = class_counts[class_counts >= 2].index
removed_classes = class_counts[class_counts < 2]

if len(removed_classes) > 0:
    print("\nClasses excluded because they have fewer than 2 samples:")
    print(removed_classes)

mask = y.isin(valid_classes)
X = X.loc[mask].reset_index(drop=True)
y = y.loc[mask].reset_index(drop=True)

if y.nunique() < 2:
    raise RuntimeError("Fewer than two usable classes remain.")

# --------------------------------------------------
# LABEL ENCODING
# --------------------------------------------------

encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)
class_names = encoder.classes_.tolist()

print("\nFinal classes:")
for i, name in enumerate(class_names):
    print(f" {i}: {name}")

# --------------------------------------------------
# TRAIN / TEST SPLIT
# --------------------------------------------------

final_counts = pd.Series(y).value_counts()
can_stratify = final_counts.min() >= 2

if can_stratify:
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_encoded,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y_encoded,
    )
else:
    print("\nWARNING: Stratified split unavailable.")
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_encoded,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

print("\nDataset split:")
print("Training:", len(X_train))
print("Testing :", len(X_test))

# --------------------------------------------------
# CLASS WEIGHTS
# --------------------------------------------------

train_counts = np.bincount(y_train, minlength=len(class_names))

total_train = len(y_train)
class_weights = {}

for class_id, count in enumerate(train_counts):
    if count > 0:
        class_weights[class_id] = total_train / (len(class_names) * count)

sample_weights = np.array([class_weights[int(label)] for label in y_train])

# --------------------------------------------------
# TRAIN XGBOOST
# --------------------------------------------------

print("\nTraining XGBoost...")

model = XGBClassifier(
    n_estimators=250,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.85,
    colsample_bytree=0.85,
    objective="multi:softprob",
    num_class=len(class_names),
    eval_metric="mlogloss",
    random_state=RANDOM_STATE,
    n_jobs=-1,
)

model.fit(X_train, y_train, sample_weight=sample_weights)

# --------------------------------------------------
# PREDICTION
# --------------------------------------------------

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)

report = classification_report(
    y_test,
    y_pred,
    labels=list(range(len(class_names))),
    target_names=class_names,
    output_dict=True,
    zero_division=0,
)

matrix = confusion_matrix(
    y_test,
    y_pred,
    labels=list(range(len(class_names))),
)

# --------------------------------------------------
# RESULTS
# --------------------------------------------------

print("\n" + "=" * 60)
print("MODEL VALIDATION")
print("=" * 60)

print(f"\nAccuracy: {accuracy:.4f}")

print("\nClassification report:")
print(
    classification_report(
        y_test,
        y_pred,
        labels=list(range(len(class_names))),
        target_names=class_names,
        zero_division=0,
    )
)

print("\nConfusion matrix:")
print(matrix)

# --------------------------------------------------
# SAVE MODEL
# --------------------------------------------------

Path("ai").mkdir(parents=True, exist_ok=True)
model.save_model(MODEL_PATH)

print(f"\nModel saved to:\n{MODEL_PATH}")

# --------------------------------------------------
# SAVE TRAINING METADATA
# --------------------------------------------------

results = {
    "model": "XGBoost",
    "target": "evidence_label",
    "label_type": "weak/evidence-based labels",
    "ground_truth": False,
    "total_merged_sites": int(before),
    "excluded_unknown_or_invalid": int(excluded),
    "usable_sites": int(len(df)),
    "classes": class_names,
    "class_distribution": {str(k): int(v) for k, v in y.value_counts().items()},
    "features": feature_columns,
    "feature_count": len(feature_columns),
    "train_samples": int(len(X_train)),
    "test_samples": int(len(X_test)),
    "accuracy": float(accuracy),
    "classification_report": report,
    "confusion_matrix": matrix.tolist(),
    "model_path": MODEL_PATH,
    "note": (
        "Metrics measure agreement with evidence-based weak labels, not ground-truth real-world accuracy."
    ),
}

with open(RESULTS_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Training results saved to:\n{RESULTS_PATH}")

print("\n" + "=" * 60)
print("STEP 23 COMPLETE")
print("=" * 60)
