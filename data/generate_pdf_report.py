import json
from pathlib import Path

import duckdb
import h3
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "agninetra.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "pdf_reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with duckdb.connect(str(DB_PATH)) as conn:
    sites = conn.execute(
        """
        SELECT
            h3_cell,
            detection_count,
            active_days,
            first_detection,
            last_detection,
            avg_frp,
            max_frp,
            persistence_score,
            risk_score,
            priority,
            classification,
            classification_confidence,
            nightfire_match,
            nightfire_matches,
            no2_mean,
            no2_max,
            ml_classification,
            ml_confidence,
            ml_model
        FROM persistent_firms_sites
        ORDER BY risk_score DESC
        """
    ).fetchall()

    shap_data = conn.execute(
        """
        SELECT h3_cell, prediction, explanations
        FROM shap_explanations
        """
    ).fetchall()

shap_lookup = {}
for h3_cell, prediction, explanations in shap_data:
    if isinstance(explanations, str):
        try:
            explanations = json.loads(explanations)
        except json.JSONDecodeError:
            explanations = []
    shap_lookup[h3_cell] = {
        "prediction": prediction,
        "explanations": explanations or [],
    }

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "TitleCustom",
    parent=styles["Title"],
    alignment=TA_CENTER,
    fontSize=20,
    spaceAfter=12,
)
heading_style = ParagraphStyle(
    "HeadingCustom",
    parent=styles["Heading2"],
    fontSize=14,
    spaceBefore=12,
    spaceAfter=8,
)
normal_style = ParagraphStyle(
    "NormalCustom",
    parent=styles["BodyText"],
    fontSize=9,
    leading=13,
)


def make_table(rows, widths, header=False):
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    else:
        commands.append(("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"))

    table = Table(rows, colWidths=widths)
    table.setStyle(TableStyle(commands))
    return table


def make_report(site):
    (
        h3_cell,
        detection_count,
        active_days,
        first_detection,
        last_detection,
        avg_frp,
        max_frp,
        persistence_score,
        risk_score,
        priority,
        classification,
        classification_confidence,
        nightfire_match,
        nightfire_matches,
        no2_mean,
        no2_max,
        ml_classification,
        ml_confidence,
        ml_model,
    ) = site

    latitude, longitude = h3.cell_to_latlng(h3_cell)
    output_path = OUTPUT_DIR / f"{h3_cell}.pdf"
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = [
        Paragraph("AGNINETRA", title_style),
        Paragraph("THERMAL INTELLIGENCE INVESTIGATION REPORT", heading_style),
        Spacer(1, 8),
        Paragraph(
            "<b>Important:</b> This report is an AI-assisted investigation aid "
            "based on satellite and contextual evidence. It is not a ground-truth "
            "determination.",
            normal_style,
        ),
        Spacer(1, 12),
        Paragraph("1. SITE IDENTIFICATION", heading_style),
        make_table([
            ["H3 Site", str(h3_cell)],
            ["Latitude", f"{latitude:.6f}"],
            ["Longitude", f"{longitude:.6f}"],
            ["Observation period", f"{first_detection} -> {last_detection}"],
        ], [150, 350]),
        Paragraph("2. THERMAL ACTIVITY", heading_style),
        make_table([
            ["Detections", str(detection_count)],
            ["Active days", str(active_days)],
            ["Persistence", f"{persistence_score:.2f}"],
            ["Average FRP", f"{avg_frp:.2f} MW"],
            ["Peak FRP", f"{max_frp:.2f} MW"],
        ], [150, 350]),
        Paragraph("3. PROBABLE SOURCE CLASSIFICATION", heading_style),
        make_table([
            ["Probable source", str(ml_classification)],
            ["Model confidence", f"{ml_confidence * 100:.1f}%"],
            ["Model", str(ml_model)],
            ["Previous heuristic", f"{classification} ({classification_confidence * 100:.1f}%)"],
            ["Risk score", f"{risk_score:.2f}/100"],
            ["Priority", str(priority)],
        ], [150, 350]),
        Paragraph("4. MULTI-SOURCE EVIDENCE", heading_style),
        make_table([
            ["VIIRS Nightfire match", "YES" if nightfire_match else "NO"],
            ["Nightfire matches", str(nightfire_matches)],
            ["TROPOMI NO2 contextual mean", str(no2_mean) if no2_mean is not None else "N/A"],
            ["TROPOMI NO2 contextual maximum", str(no2_max) if no2_max is not None else "N/A"],
        ], [200, 300]),
        Paragraph("5. AI DECISION EVIDENCE", heading_style),
    ]

    explanation = shap_lookup.get(h3_cell)
    if explanation:
        story.extend([
            Paragraph(f"<b>Model prediction:</b> {explanation['prediction']}", normal_style),
            Spacer(1, 8),
        ])
        shap_rows = [["Feature", "SHAP contribution", "Direction"]]
        for item in explanation["explanations"][:8]:
            value = float(item.get("shap_value", 0))
            shap_rows.append([
                str(item.get("feature", "")),
                f"{value:+.4f}",
                str(item.get("direction", "")).upper(),
            ])
        story.append(make_table(shap_rows, [240, 120, 120], header=True))
    else:
        story.append(Paragraph("No SHAP explanation is available.", normal_style))

    story.extend([
        Spacer(1, 18),
        Paragraph(
            "<b>Interpretation:</b> AgniNetra combines repeated thermal "
            "observations with contextual satellite evidence to prioritize sites "
            "for further investigation. The probable source classification and model "
            "confidence do not constitute ground-truth verification or regulatory "
            "enforcement evidence.",
            normal_style,
        ),
    ])
    doc.build(story)
    return output_path


print("=" * 60)
print("AGNINETRA PDF REPORT GENERATION")
print("=" * 60)

generated = 0
for site in sites:
    try:
        make_report(site)
        generated += 1
    except Exception as error:
        print(f"ERROR: {site[0]} -> {error}")

print()
print(f"PDF reports generated: {generated}")
print(f"Output directory: {OUTPUT_DIR.relative_to(PROJECT_ROOT).as_posix()}")
print("=" * 60)
