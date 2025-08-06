from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class FrontData(BaseModel):
    idNumber: str
    lastName: str
    firstName: str
    fatherFullName: str
    dateOfBirth: str  # Format: YYYY/MM/DD
    placeOfBirth: str


class BackData(BaseModel):
    motherFullName: str
    job: str
    address: str
    dateOfCreation: str  # Format: YYYY/MM/DD


class SideStatus(BaseModel):
    status: Literal["Valid", "Invalid"]
    data: Optional[dict] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_data_on_status(cls, instance):
        if instance.status == "Valid":
            if not instance.data or not isinstance(instance.data, dict) or len(instance.data) == 0:
                raise ValueError("If status is 'Valid', 'data' must be a non-empty dict.")
        elif instance.status == "Invalid":
            if instance.data and len(instance.data) > 0:
                raise ValueError("If status is 'Invalid', 'data' must be an empty dict.")
        return instance


class TunisianIDCardResponse(BaseModel):
    front: SideStatus
    back: SideStatus

    @model_validator(mode="after")
    def validate_fields_structure(cls, instance):
        if instance.front.status == "Valid":
            try:
                FrontData(**instance.front.data)
            except Exception as e:
                raise ValueError(f"Front data does not match expected fields: {str(e)}")

        if instance.back.status == "Valid":
            try:
                BackData(**instance.back.data)
            except Exception as e:
                raise ValueError(f"Back data does not match expected fields: {str(e)}")

        return instance
