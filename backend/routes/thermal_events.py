import h3
from fastapi import APIRouter

from backend.database import insert_thermal_event, list_thermal_events
from backend.models import ThermalEvent

router = APIRouter()


@router.post("/thermal-event")
def create_thermal_event(event: ThermalEvent):
    h3_cell = h3.latlng_to_cell(event.latitude, event.longitude, 8)
    stored_event = insert_thermal_event(event.model_dump(), h3_cell)
    return {
        "message": "Thermal event stored successfully",
        **stored_event,
    }


@router.get("/thermal-events")
def get_thermal_events():
    return {
        "events": list_thermal_events(),
    }
