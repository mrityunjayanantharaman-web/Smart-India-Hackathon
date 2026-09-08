from pathlib import Path

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
OUTPUT_CSV = PROJECT_ROOT / "data" / "processed" / "evidence_labels.csv"


def score_industrial(row):
    score = 0.0
    reasons = []

    if row["nightfire_matches"] and row["nightfire_matches"] > 0:
        score += 0.45 + min(row["nightfire_matches"], 3) * 0.10
        reasons.append(f"Nightfire match: {int(row['nightfire_matches'])}")

    if row["persistence_score"] >= 0.70:
        score += 0.18
        reasons.append(f"High persistence ({row['persistence_score']:.2f})")
    elif row["persistence_score"] >= 0.50:
        score += 0.10
        reasons.append(f"Moderate persistence ({row['persistence_score']:.2f})")

    if row["detection_count"] >= 8:
        score += 0.10
        reasons.append(f"Repeated thermal detections ({int(row['detection_count'])})")
    elif row["detection_count"] >= 5:
        score += 0.06
        reasons.append(f"Consistent detections ({int(row['detection_count'])})")

    if row["no2_mean"] is not None and row["no2_mean"] > 0:
        if row["no2_mean"] >= 40e-6:
            score += 0.15
            reasons.append(f"Elevated NO2 mean ({row['no2_mean']:.2e})")
        elif row["no2_mean"] >= 20e-6:
            score += 0.08
            reasons.append(f"Moderate NO2 mean ({row['no2_mean']:.2e})")

    if row["built_up_ratio"] >= 0.60:
        score += 0.10
        reasons.append(f"Built-up land cover ({row['built_up_ratio']:.2f})")
    elif row["built_up_ratio"] >= 0.35:
        score += 0.06
        reasons.append(f"Mixed built-up context ({row['built_up_ratio']:.2f})")

    if row["nearby_power_plants_10km"] >= 3:
        score += 0.10
        reasons.append(f"Power plants nearby ({int(row['nearby_power_plants_10km'])})")
    elif row["nearby_power_plants_10km"] >= 1:
        score += 0.05
        reasons.append(f"Some nearby power plants ({int(row['nearby_power_plants_10km'])})")

    if row["max_frp"] >= 10:
        score += 0.05
        reasons.append(f"Strong FRP peaks ({row['max_frp']:.2f})")

    return min(1.0, score), reasons


def score_agricultural(row):
    score = 0.0
    reasons = []

    if row["cropland_ratio"] >= 0.30:
        score += 0.35
        reasons.append(f"Strong cropland signal ({row['cropland_ratio']:.2f})")
    elif row["cropland_ratio"] >= 0.10:
        score += 0.20
        reasons.append(f"Notable cropland signal ({row['cropland_ratio']:.2f})")

    if row["detection_count"] > 0:
        daytime_share = row["daytime_detections"] / row["detection_count"]
        if daytime_share >= 0.55:
            score += 0.20
            reasons.append(f"Predominantly daytime detections ({daytime_share:.2f})")
        elif daytime_share >= 0.40:
            score += 0.12
            reasons.append(f"Daytime-heavy detections ({daytime_share:.2f})")

    if row["avg_frp"] is not None and row["avg_frp"] <= 8.0:
        score += 0.12
        reasons.append(f"Lower/moderate FRP ({row['avg_frp']:.2f})")
    elif row["avg_frp"] is not None and row["avg_frp"] <= 12.0:
        score += 0.06
        reasons.append(f"Moderate FRP ({row['avg_frp']:.2f})")

    if row["persistence_score"] < 0.70:
        score += 0.15
        reasons.append(f"Lower persistence ({row['persistence_score']:.2f})")

    if row["built_up_ratio"] < 0.35 and row["cropland_ratio"] > 0:
        score += 0.10
        reasons.append("Weak industrial context")

    return min(1.0, score), reasons


def score_wildfire(row):
    score = 0.0
    reasons = []

    if row["max_frp"] >= 20:
        score += 0.35
        reasons.append(f"High FRP peak ({row['max_frp']:.2f})")
    elif row["max_frp"] >= 10:
        score += 0.20
        reasons.append(f"Elevated FRP ({row['max_frp']:.2f})")

    if row["persistence_score"] < 0.60:
        score += 0.20
        reasons.append(f"Short-lived activity ({row['persistence_score']:.2f})")

    wildland_score = (
        row["tree_cover_ratio"]
        + row["grassland_ratio"]
        + row["bare_land_ratio"]
    )
    if wildland_score >= 0.50:
        score += 0.25
        reasons.append(f"Wildland context ({wildland_score:.2f})")
    elif wildland_score >= 0.25:
        score += 0.15
        reasons.append(f"Mixed wildland context ({wildland_score:.2f})")

    if row["detection_count"] <= 6 and row["max_frp"] >= 8:
        score += 0.10
        reasons.append("Short, intense thermal burst")

    return min(1.0, score), reasons


def assign_label(industrial_score, agricultural_score, wildfire_score):
    scores = {
        "Industrial": industrial_score,
        "Agricultural": agricultural_score,
        "Wildfire": wildfire_score,
    }
    best_label, best_score = max(scores.items(), key=lambda item: item[1])
    second_best = sorted(scores.values(), reverse=True)[1]

    if best_score < 0.50:
        return "Unknown", "Low", best_score, second_best

    if best_label == "Industrial" and industrial_score >= agricultural_score + 0.15 and industrial_score >= wildfire_score + 0.15:
        return "Industrial", "High" if best_score >= 0.75 else "Medium" if best_score >= 0.60 else "Low", best_score, second_best
    if best_label == "Agricultural" and agricultural_score >= industrial_score + 0.15 and agricultural_score >= wildfire_score + 0.15:
        return "Agricultural", "High" if best_score >= 0.75 else "Medium" if best_score >= 0.60 else "Low", best_score, second_best
    if best_label == "Wildfire" and wildfire_score >= industrial_score + 0.15 and wildfire_score >= agricultural_score + 0.15:
        return "Wildfire", "High" if best_score >= 0.75 else "Medium" if best_score >= 0.60 else "Low", best_score, second_best

    return "Unknown", "Low", best_score, second_best


def main():
    conn = duckdb.connect(str(DB_PATH))

    site_query = """
        WITH nightfire_counts AS (
            SELECT h3_cell, COUNT(*) AS nightfire_matches
            FROM nightfire_sites
            GROUP BY h3_cell
        )
        SELECT
            p.h3_cell,
            p.detection_count,
            p.active_days,
            p.persistence_score,
            p.avg_frp,
            p.max_frp,
            p.daytime_detections,
            p.nighttime_detections,
            p.nightfire_match,
            COALESCE(nc.nightfire_matches, 0) AS nightfire_matches,
            p.no2_mean,
            p.no2_max,
            COALESCE(c.built_up_ratio, 0) AS built_up_ratio,
            COALESCE(c.cropland_ratio, 0) AS cropland_ratio,
            COALESCE(c.tree_cover_ratio, 0) AS tree_cover_ratio,
            COALESCE(c.grassland_ratio, 0) AS grassland_ratio,
            COALESCE(c.bare_land_ratio, 0) AS bare_land_ratio,
            COALESCE(c.nearby_power_plants_10km, 0) AS nearby_power_plants_10km,
            COALESCE(c.industrial_context_score, 0) AS industrial_context_score,
            COALESCE(c.wildland_context_score, 0) AS wildland_context_score
        FROM persistent_firms_sites p
        LEFT JOIN nightfire_counts nc
            ON p.h3_cell = nc.h3_cell
        LEFT JOIN context_features c
            ON p.h3_cell = c.h3_cell
    """

    site_df = conn.execute(site_query).fetchdf()
    site_df = site_df.fillna(0)

    label_rows = []
    for _, row in site_df.iterrows():
        industrial_score, industrial_reasons = score_industrial(row)
        agricultural_score, agricultural_reasons = score_agricultural(row)
        wildfire_score, wildfire_reasons = score_wildfire(row)

        label, confidence, best_score, second_best = assign_label(
            industrial_score, agricultural_score, wildfire_score
        )

        if label == "Industrial":
            reasons = industrial_reasons
        elif label == "Agricultural":
            reasons = agricultural_reasons
        elif label == "Wildfire":
            reasons = wildfire_reasons
        else:
            reasons = [
                *industrial_reasons[:2],
                *agricultural_reasons[:2],
                *wildfire_reasons[:2],
            ]
            if not reasons:
                reasons = ["Insufficient evidence or contradictory signals"]

        label_rows.append(
            {
                "h3_cell": row["h3_cell"],
                "evidence_label": label,
                "evidence_confidence": confidence,
                "industrial_evidence_score": round(float(industrial_score), 4),
                "agricultural_evidence_score": round(float(agricultural_score), 4),
                "wildfire_evidence_score": round(float(wildfire_score), 4),
                "evidence_reasons": "; ".join(reasons),
            }
        )

    evidence_df = pd.DataFrame(label_rows)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    evidence_df.to_csv(OUTPUT_CSV, index=False)

    conn.register("evidence_df", evidence_df)
    conn.execute("DROP TABLE IF EXISTS evidence_labels")
    conn.execute("CREATE TABLE evidence_labels AS SELECT * FROM evidence_df")

    print("Evidence labels created:", len(evidence_df))
    print("CSV:", OUTPUT_CSV)
    print("DuckDB table: evidence_labels")

    label_counts = evidence_df["evidence_label"].value_counts().sort_index()
    print("\nLabel counts:")
    for label, count in label_counts.items():
        print(f"  {label}: {count}")

    confidence_counts = evidence_df["evidence_confidence"].value_counts().sort_index()
    print("\nConfidence counts:")
    for level, count in confidence_counts.items():
        print(f"  {level}: {count}")

    unknown_count = int((evidence_df["evidence_label"] == "Unknown").sum())
    print(f"\nUnknown sites: {unknown_count}")

    print("\nTop 10 Industrial candidates:")
    industrial_top = evidence_df.sort_values("industrial_evidence_score", ascending=False).head(10)
    for _, row in industrial_top.iterrows():
        print(
            f"  {row['h3_cell']} | score={row['industrial_evidence_score']} | "
            f"label={row['evidence_label']} | confidence={row['evidence_confidence']} | "
            f"reasons={row['evidence_reasons']}"
        )

    print("\nTop 10 Agricultural candidates:")
    agri_top = evidence_df.sort_values("agricultural_evidence_score", ascending=False).head(10)
    for _, row in agri_top.iterrows():
        print(
            f"  {row['h3_cell']} | score={row['agricultural_evidence_score']} | "
            f"label={row['evidence_label']} | confidence={row['evidence_confidence']} | "
            f"reasons={row['evidence_reasons']}"
        )

    print("\nTop 10 Wildfire candidates:")
    wildfire_top = evidence_df.sort_values("wildfire_evidence_score", ascending=False).head(10)
    for _, row in wildfire_top.iterrows():
        print(
            f"  {row['h3_cell']} | score={row['wildfire_evidence_score']} | "
            f"label={row['evidence_label']} | confidence={row['evidence_confidence']} | "
            f"reasons={row['evidence_reasons']}"
        )

    conn.close()


if __name__ == "__main__":
    main()
