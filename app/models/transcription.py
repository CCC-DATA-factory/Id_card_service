from pydantic import BaseModel


class TranscriptionRequest(BaseModel):
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

