from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {
        "system": "AgniNetra",
        "status": "online",
        "message": "From satellite fire dots to real-world action.",
    }


@router.get("/health")
def health():
    return {
        "status": "healthy",
    }
