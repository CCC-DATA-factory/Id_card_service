from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime


class FrontData(BaseModel):
    idNumber: str
    lastName: str
    firstName: str
    fatherFullName: str
    dateOfBirth: str  
    placeOfBirth: str

    @field_validator('idNumber')
    @classmethod
    def validate_id_number(cls, v: str) -> str:
        """Validate idNumber is exactly 8 digits"""
        if not v:
            raise ValueError("idNumber cannot be empty")
        
        # Remove any whitespace
        v = v.strip()
        
        # Check if it's exactly 8 characters and all digits
        if len(v) != 8:
            raise ValueError(f"idNumber must be exactly 8 digits, got {len(v)}")
        
        if not v.isdigit():
            raise ValueError("idNumber must contain only digits")
        
        return v

    @field_validator('dateOfBirth')
    @classmethod
    def validate_date_of_birth(cls, v: str) -> str:
        """Validate dateOfBirth is in YYYY/MM/DD format and is a valid date"""
        if not v:
            raise ValueError("dateOfBirth cannot be empty")
        
        try:
            # Try to parse the date
            datetime.strptime(v, "%Y/%m/%d")
        except ValueError:
            raise ValueError(f"dateOfBirth must be in YYYY/MM/DD format, got '{v}'")
        
        return v

    @field_validator('lastName', 'firstName', 'fatherFullName', 'placeOfBirth')
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure fields are not empty"""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class BackData(BaseModel):
    motherFullName: str
    job: str
    address: str
    dateOfCreation: str

    @field_validator('dateOfCreation')
    @classmethod
    def validate_date_of_creation(cls, v: str) -> str:
        """Validate dateOfCreation is in YYYY/MM/DD format and is a valid date"""
        if not v:
            raise ValueError("dateOfCreation cannot be empty")
        
        try:
            # Try to parse the date
            datetime.strptime(v, "%Y/%m/%d")
        except ValueError:
            raise ValueError(f"dateOfCreation must be in YYYY/MM/DD format, got '{v}'")
        
        return v

    @field_validator('motherFullName', 'job', 'address')
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure fields are not empty"""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class SideStatus(BaseModel):
    status: Literal["Valid", "Invalid"]
    data: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_data_on_status(self):
        """Ensure data is empty for Invalid and non-empty for Valid"""
        if self.status == "Valid":
            if not self.data or len(self.data) == 0:
                # Auto-correct: if status is Valid but data is empty, mark as Invalid
                self.status = "Invalid"
                self.data = {}
        elif self.status == "Invalid":
            # Ensure data is empty for Invalid status
            self.data = {}
        return self


class TunisianIDCardResponse(BaseModel):
    front: SideStatus
    back: SideStatus

    @model_validator(mode="after")
    def validate_and_sanitize_fields(self):
        """
        Validate field structure and data types.
        If validation fails, automatically mark the side as Invalid.
        This ensures NO errors are raised - just marks sides as Invalid.
        """
        # Validate FRONT side
        if self.front.status == "Valid" and self.front.data:
            try:
                # Try to validate against FrontData schema
                FrontData(**self.front.data)
            except Exception as e:
                # Validation failed - mark front as Invalid
                print(f"Front validation failed: {str(e)}")
                self.front.status = "Invalid"
                self.front.data = {}

        # Validate BACK side
        if self.back.status == "Valid" and self.back.data:
            try:
                # Try to validate against BackData schema
                BackData(**self.back.data)
            except Exception as e:
                # Validation failed - mark back as Invalid
                print(f"Back validation failed: {str(e)}")
                self.back.status = "Invalid"
                self.back.data = {}

        return self