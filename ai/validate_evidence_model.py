import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    classification_report,
    confusion_matrix,
)

from xgboost import XGBClassifier

# ============================================================
# CONFIG
# ============================================================

DB_PATH = "data/processed/agninetra.duckdb"
RESULT_PATH = "ai/evidence_model_validation.json"

RANDOM_STATE = 42
MAX_FOLDS = 5

# ============================================================
# LOAD DATA
# ============================================================

print("=" * 65)
print("AGNI NETRA - STEP 24")
print("STRONGER EVIDENCE-BASED MODEL VALIDATION")
print("=" * 65)

conn = duckdb.connect(DB_PATH)

features = conn.execute("""
    SELECT *
    FROM thermal_site_features
""").fetchdf()

context = conn.execute("""
    SELECT *
    FROM context_features
""").fetchdf()

labels = conn.execute("""
    SELECT *
    FROM evidence_labels
""").fetchdf()

conn.close()

print("\nLoaded:")
print("Thermal features:", len(features))
print("Context features:", len(context))
print("Evidence labels:", len(labels))

# ============================================================
# MERGE
# ============================================================

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

print("Merged rows:", len(df))

# ============================================================
# REMOVE UNKNOWN / INVALID LABELS
# ============================================================

unknown_values = {"Unknown", "UNKNOWN", "unknown", "", "None", "nan", None}

df = df[
    df["evidence_label"].notna() & ~df["evidence_label"].isin(unknown_values)
].copy()

print("\nUsable labeled rows:", len(df))

print("\nEvidence label distribution:")
print(df["evidence_label"].value_counts())

# ============================================================
# FEATURE SELECTION
# ============================================================

EXCLUDED = {
    # Identifiers
    "h3_cell",
    "latitude",
    "longitude",

    # Old model outputs
    "classification",
    "classification_confidence",
    "source_scores",

    # Risk outputs
    "risk_score",
    "priority",

    # New target
    "evidence_label",
    "evidence_confidence",
    "evidence_score",

    # Evidence target components
    "industrial_evidence_score",
    "agricultural_evidence_score",
    "wildfire_evidence_score",
    "evidence_reasons",

    # OSM unavailable
    "osm_industrial_features",
}

numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()

feature_columns = [
    col for col in numeric_columns if col not in EXCLUDED
]

print("\nFeatures used:")
for col in feature_columns:
    print(" -", col)

print("\nTotal features:", len(feature_columns))

# ============================================================
# BUILD X / y
# ============================================================

X = df[feature_columns].copy()

X = X.replace([np.inf, -np.inf], np.nan)

# Fill missing values column-by-column
for col in X.columns:
    if X[col].isna().all():
        X[col] = 0
    else:
        X[col] = X[col].fillna(X[col].median())

X = X.fillna(0)

y_text = df["evidence_label"].astype(str)

encoder = LabelEncoder()
y = encoder.fit_transform(y_text)

class_names = encoder.classes_.tolist()

print("\nClasses:")
for i, name in enumerate(class_names):
    print(f" {i}: {name}")

# ============================================================
# CHECK CLASS SIZES
# ============================================================

class_counts = pd.Series(y_text).value_counts()

print("\nClass sizes:")
print(class_counts)

minimum_class_size = int(class_counts.min())

if minimum_class_size < 2:
    raise RuntimeError(
        "At least one class has fewer than 2 samples. "
        "Cross-validation cannot be performed reliably."
    )

n_splits = min(MAX_FOLDS, minimum_class_size)

if n_splits < 2:
    raise RuntimeError("Not enough samples for cross-validation.")

print(f"\nUsing {n_splits}-fold stratified cross-validation.")

# ============================================================
# CROSS VALIDATION
# ============================================================

skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)

fold_results = []

overall_true = []
overall_pred = []

print("\n" + "=" * 65)
print("CROSS-VALIDATION")
print("=" * 65)

for fold_number, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]

    y_train = y[train_idx]
    y_test = y[test_idx]

    # --------------------------------------------------------
    # Class weights
    # --------------------------------------------------------

    train_counts = np.bincount(y_train, minlength=len(class_names))
    total_train = len(y_train)

    weights = {}

    for class_id, count in enumerate(train_counts):
        if count > 0:
            weights[class_id] = total_train / (len(class_names) * count)

    sample_weights = np.array([weights[int(label)] for label in y_train])

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    predictions = model.predict(X_test)

    overall_true.extend(y_test.tolist())
    overall_pred.extend(predictions.tolist())

    accuracy = accuracy_score(y_test, predictions)
    balanced_accuracy = balanced_accuracy_score(y_test, predictions)
    macro_f1 = f1_score(y_test, predictions, average="macro", zero_division=0)
    macro_precision = precision_score(y_test, predictions, average="macro", zero_division=0)
    macro_recall = recall_score(y_test, predictions, average="macro", zero_division=0)

    fold_results.append(
        {
            "fold": fold_number,
            "train_samples": len(train_idx),
            "test_samples": len(test_idx),
            "accuracy": float(accuracy),
            "balanced_accuracy": float(balanced_accuracy),
            "macro_f1": float(macro_f1),
            "macro_precision": float(macro_precision),
            "macro_recall": float(macro_recall),
        }
    )

    print(f"\nFold {fold_number}:")
    print(f"  Accuracy:           {accuracy:.4f}")
    print(f"  Balanced Accuracy:  {balanced_accuracy:.4f}")
    print(f"  Macro Precision:    {macro_precision:.4f}")
    print(f"  Macro Recall:       {macro_recall:.4f}")
    print(f"  Macro F1:           {macro_f1:.4f}")

# ============================================================
# OVERALL CROSS-VALIDATED METRICS
# ============================================================

overall_true = np.array(overall_true)
overall_pred = np.array(overall_pred)

overall_accuracy = accuracy_score(overall_true, overall_pred)
overall_balanced_accuracy = balanced_accuracy_score(overall_true, overall_pred)
overall_macro_precision = precision_score(overall_true, overall_pred, average="macro", zero_division=0)
overall_macro_recall = recall_score(overall_true, overall_pred, average="macro", zero_division=0)
overall_macro_f1 = f1_score(overall_true, overall_pred, average="macro", zero_division=0)

overall_matrix = confusion_matrix(overall_true, overall_pred, labels=list(range(len(class_names))))
overall_report = classification_report(
    overall_true,
    overall_pred,
    labels=list(range(len(class_names))),
    target_names=class_names,
    zero_division=0,
)

# ============================================================
# FOLD STATISTICS
# ============================================================

fold_df = pd.DataFrame(fold_results)

metric_names = [
    "accuracy",
    "balanced_accuracy",
    "macro_precision",
    "macro_recall",
    "macro_f1",
]

fold_statistics = {}

for metric in metric_names:
    fold_statistics[metric] = {
        "mean": float(fold_df[metric].mean()),
        "std": float(fold_df[metric].std(ddof=1)) if len(fold_df) > 1 else 0.0,
        "min": float(fold_df[metric].min()),
        "max": float(fold_df[metric].max()),
    }

# ============================================================
# PRINT FINAL RESULTS
# ============================================================

print("\n" + "=" * 65)
print("OVERALL CROSS-VALIDATED RESULTS")
print("=" * 65)

print(f"\nAccuracy:           {overall_accuracy:.4f}")
print(f"Balanced Accuracy:  {overall_balanced_accuracy:.4f}")
print(f"Macro Precision:    {overall_macro_precision:.4f}")
print(f"Macro Recall:       {overall_macro_recall:.4f}")
print(f"Macro F1:           {overall_macro_f1:.4f}")

print("\nClassification report:")
print(overall_report)

print("Confusion matrix:")
print(overall_matrix)

print("\nFold stability:")
for metric in metric_names:
    stats = fold_statistics[metric]
    print(
        f"{metric}: mean={stats['mean']:.4f}, std={stats['std']:.4f}, min={stats['min']:.4f}, max={stats['max']:.4f}"
    )

# ============================================================
# SAVE RESULTS
# ============================================================

Path("ai").mkdir(parents=True, exist_ok=True)

results = {
    "validation_type": "stratified_k_fold",
    "folds": n_splits,
    "target": "evidence_label",
    "label_type": "weak/evidence-based labels",
    "ground_truth": False,
    "total_sites_after_merge": int(len(df)),
    "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
    "classes": class_names,
    "features": feature_columns,
    "feature_count": len(feature_columns),
    "overall_metrics": {
        "accuracy": float(overall_accuracy),
        "balanced_accuracy": float(overall_balanced_accuracy),
        "macro_precision": float(overall_macro_precision),
        "macro_recall": float(overall_macro_recall),
        "macro_f1": float(overall_macro_f1),
    },
    "fold_statistics": fold_statistics,
    "fold_results": fold_results,
    "classification_report": classification_report(
        overall_true,
        overall_pred,
        labels=list(range(len(class_names))),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    ),
    "confusion_matrix": overall_matrix.tolist(),
    "note": (
        "Metrics measure agreement with evidence-based weak labels and are not ground-truth real-world accuracy. "
        "The dataset is small, so results should be treated as provisional."
    ),
}

with open(RESULT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\nValidation results saved to:\n{RESULT_PATH}")

print("\n" + "=" * 65)
print("STEP 24 COMPLETE")
print("=" * 65)
