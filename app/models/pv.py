# models/pv.py

from typing import List, Optional, Literal, Dict, Union
from pydantic import BaseModel

class AttemptInfo(BaseModel):
    timestamp: float
    key: Optional[str]
    status: Optional[Literal["success", "validation_error", "resource_exhausted", "system_error"]]
    input_tokens: int
    output_tokens: int
    error_type: Optional[str]
    error_msg: Optional[str]
    duration: Optional[float]

class FullPromptValue(BaseModel):
    total_api_calls: int
    total_input_tokens: int
    total_output_tokens: int
    attempts: List[AttemptInfo]
    keys_used: List[str]
    start_time: float
    duration_total: Optional[float]
