from typing import Literal, Optional

from pydantic import BaseModel, Field


class Identifier(BaseModel):
    partner_job_id: str
    id: Optional[str] = None
    partner_label: str


class GeoJsonPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float]


class Naf(BaseModel):
    code: str
    label: Optional[str] = None


class Domain(BaseModel):
    idcc: Optional[int] = None
    opco: Optional[str] = None
    naf: Optional[Naf] = None


class Location(BaseModel):
    address: str
    geopoint: Optional[GeoJsonPoint] = None


class Workplace(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    siret: Optional[str] = None
    location: Optional[Location] = None
    brand: Optional[str] = None
    legal_name: Optional[str] = None
    size: Optional[str] = None
    domain: Optional[Domain] = None


class Apply(BaseModel):
    phone: Optional[str] = None
    url: str = ""
    recipient_id: Optional[str] = None


class Contract(BaseModel):
    start: Optional[str] = None
    start_type: Optional[str] = None
    start_is_flexible: Optional[bool] = None
    duration: Optional[int] = None
    type: list[str] = Field(default_factory=list)
    remote: Optional[str] = None


class Publication(BaseModel):
    creation: Optional[str] = None
    expiration: Optional[str] = None


class TargetDiploma(BaseModel):
    european: Optional[str] = None
    label: Optional[str] = None


class Offer(BaseModel):
    title: str
    description: str = ""
    desired_skills: list[str] = Field(default_factory=list)
    to_be_acquired_skills: list[str] = Field(default_factory=list)
    access_conditions: list[str] = Field(default_factory=list)
    opening_count: Optional[int] = None
    publication: Optional[Publication] = None
    rome_codes: list[str] = Field(default_factory=list)
    target_diploma: Optional[TargetDiploma] = None
    status: Optional[str] = None
    to_applicant_questions: Optional[list[str]] = None


class JobOffer(BaseModel):
    identifier: Identifier
    workplace: Optional[Workplace] = None
    apply: Optional[Apply] = None
    contract: Optional[Contract] = None
    offer: Offer
    is_delegated: bool = False

    @property
    def id(self) -> Optional[str]:
        return self.identifier.id or self.identifier.partner_job_id
