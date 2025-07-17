from typing import Any, Dict, List
from pydantic import BaseModel, field_validator
import re
import regex as re

from models.pv import FullPromptValue

LATIN_ALLOWED_PATTERN = re.compile(
    r"^[\p{Latin}0-9\s\.,:\-()/]+$",
    re.UNICODE | re.VERBOSE
)
ARABIC_ALLOWED_PATTERN = re.compile(r'^[\u0600-\u06FF0-9\s\.,:\-()/]+$')


class TunisianIDCardData(BaseModel):
    idNumber: str
    lastName: str
    firstName: str
    fatherFullName: str
    dateOfBirth: str
    placeOfBirth: str
    motherFullName: str
    job: str
    address: str
    dateOfCreation: str

    @field_validator('*')
    @classmethod
    def validate_latin_characters(cls, value, info):
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a string")
        if not LATIN_ALLOWED_PATTERN.fullmatch(value):
            raise ValueError(f"{info.field_name} must only contain Latin letters, digits, and allowed symbols.")
        return value


class TunisianIDCardFront(BaseModel):
    idNumber: str
    lastName: str
    firstName: str
    fatherFullName: str
    dateOfBirth: str
    placeOfBirth: str

    @field_validator('*')
    @classmethod
    def validate_arabic_characters(cls, value, info):
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a string")
        if not ARABIC_ALLOWED_PATTERN.fullmatch(value):
            raise ValueError(f"{info.field_name} must only contain Arabic letters, digits, and allowed symbols.")
        return value

class TunisianIDCardBack(BaseModel):
    motherFullName: str
    job: str
    address: str
    dateOfCreation: str

    @field_validator('*')
    @classmethod
    def validate_arabic_characters(cls, value, info):
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a string")
        if not ARABIC_ALLOWED_PATTERN.fullmatch(value):
            raise ValueError(f"{info.field_name} must only contain Arabic letters, digits, and allowed symbols.")
        return value


class FrontResponse(BaseModel):
    data: TunisianIDCardFront
    audit: FullPromptValue

class BackResponse(BaseModel):
    data: TunisianIDCardBack
    audit: FullPromptValue

class TranscriptResponse(BaseModel):
    results: List[TunisianIDCardData]
    pv: FullPromptValue