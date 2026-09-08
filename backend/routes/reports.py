import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/report/{h3}")
def download_report(h3: str):
    report_path = f"data/processed/pdf_reports/{h3}.pdf"

    if not os.path.exists(report_path):
        return {
            "error": "Report not found",
            "h3_cell": h3,
        }

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=f"AgniNetra_{h3}_Investigation_Report.pdf",
    )
