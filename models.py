from pydantic import BaseModel

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

class TunisianIDCardFront(BaseModel):
    idNumber: str
    lastName: str
    firstName: str
    fatherFullName: str
    dateOfBirth: str
    placeOfBirth: str

class TunisianIDCardBack(BaseModel):
    motherFullName: str
    job: str
    address: str
    dateOfCreation: str
