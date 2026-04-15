from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class AudioMetadataRead(BaseModel):
    duration_seconds: float
    sample_rate: int
    bit_depth: int
    channels: int

    model_config = ConfigDict(from_attributes=True)
