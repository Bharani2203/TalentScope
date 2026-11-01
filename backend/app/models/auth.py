from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserType(str, Enum):
    individual = "individual"
    employee = "employee"
    company = "company"


class AuthenticatedUser(BaseModel):
    uid: str
    email: str | None = None
    email_verified: bool = False
    phone_number: str | None = None
    display_name: str | None = None
    auth_provider: str | None = None
    company_id: str | None = Field(default=None, exclude=True)
    role: str | None = Field(default=None, exclude=True)
    claims: dict[str, Any] | None = Field(default=None, exclude=True)


class AuthSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_type: UserType | None = None
    employee_type: str | None = Field(default=None, max_length=80)
    company_name: str | None = Field(default=None, max_length=200)


class UserProfile(AuthenticatedUser):
    phone_verified: bool = False
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    onboarding_completed: bool = False
    user_type: UserType | None = None
    employee_type: str | None = None
    company_name: str | None = None
    company_id: str | None = None
    role: str | None = "individual"
    avatar_url: str | None = None


class AuthUserResponse(BaseModel):
    authenticated: bool = True
    user: AuthenticatedUser


class AuthSyncResponse(BaseModel):
    authenticated: bool = True
    user: UserProfile
