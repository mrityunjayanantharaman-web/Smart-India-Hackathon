from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class ThermalEvent(BaseModel):
    latitude: float
    longitude: float
    frp: float
    brightness_temperature: float
    confidence: float
    source: str
    observation_time: datetime = Field(default_factory=datetime.now)