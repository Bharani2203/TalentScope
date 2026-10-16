from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    role: str | None = Field(default=None, max_length=120)
    team: str | None = Field(default=None, max_length=120)


class CompanyInvitationCreated(BaseModel):
    invitation_id: str
    token: str
    expires_at: datetime
    status: str = "invited"


class CompanyInvitationSummary(BaseModel):
    invitation_id: str
    company_id: str
    intended_email: str | None = None
    role: str | None = None
    team: str | None = None
    status: Literal["invited", "accepted", "declined"] | None = None
    expired: bool | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    declined_at: datetime | None = None


class CompanyInvitationToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=200)


class CompanyConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str = Field(min_length=1, max_length=160)


class CompanyConnectionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "decline"]


class CompanyConnectionReviewResponse(BaseModel):
    employee_uid: str
    company_id: str
    status: Literal["approved", "declined"]
    reviewed_by: str
    reviewed_at: datetime


class CompanyDirectoryEntry(BaseModel):
    company_id: str
    company_name: str | None = None
    industry: str | None = None
    hq_region: dict | None = None


class CompanyConnectionRequestItem(BaseModel):
    employee_uid: str
    company_id: str
    email: str | None = None
    status: Literal["pending"]
    created_at: datetime | None = None
