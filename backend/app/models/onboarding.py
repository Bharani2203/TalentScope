from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgeGroup(str, Enum):
    prefer_not_to_say = "Prefer not to say"
    under_18 = "Under 18"
    age_18_21 = "18–21"
    age_22_25 = "22–25"
    age_26_30 = "26–30"
    age_31_40 = "31–40"
    over_40 = "40+"


class CurrentStage(str, Enum):
    student = "Student"
    recently_graduated = "Recently graduated"
    first_job = "Looking for my first job"
    working_professional = "Working professional"
    changing_careers = "Changing careers"
    personal_growth = "Learning for personal growth"


class ExperienceLevel(str, Enum):
    none = "No experience yet"
    under_one_year = "Less than 1 year"
    one_to_two_years = "1–2 years"
    three_to_five_years = "3–5 years"
    over_five_years = "5+ years"


class SkillLevel(str, Enum):
    beginner = "Beginner"
    comfortable = "Comfortable"
    advanced = "Advanced"
    expert = "Expert"


class CareerGoal(str, Enum):
    first_job = "Get my first job"
    better_job = "Get a better job"
    current_role_growth = "Grow in my current role"
    new_role = "Move into a new role"
    change_careers = "Change careers"
    start_business = "Start a business"
    improve_skills = "Improve my skills"
    explore = "Explore opportunities"


class Interest(str, Enum):
    artificial_intelligence = "Artificial Intelligence"
    software_development = "Software Development"
    data_engineering = "Data Engineering"
    cloud_devops = "Cloud & DevOps"
    cybersecurity = "Cybersecurity"
    electronics_embedded = "Electronics & Embedded"
    healthcare_tech = "Healthcare Tech"
    fintech = "Fintech"
    design_ux = "Design & UX"
    business_analytics = "Business Analytics"
    ai_research = "AI Research"
    automation = "Automation"


class LearningStyle(str, Enum):
    short_lessons = "Short lessons"
    hands_on = "Hands-on practice"
    projects = "Projects"
    videos = "Videos"
    reading = "Reading"
    quizzes = "Quizzes"
    mentor = "Learning with a mentor"


class WeeklyLearningTime(str, Enum):
    under_two = "Less than 2 hours"
    two_to_five = "2–5 hours"
    five_to_ten = "5–10 hours"
    over_ten = "10+ hours"


class WorkPreference(str, Enum):
    remote = "Remote"
    current_city = "My current city"
    within_country = "Within my country"
    relocating = "Open to relocating"
    anywhere = "Anywhere"


class BasicProfileAnswer(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    ageGroup: AgeGroup | None = None
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=120)


class ExperienceAnswer(StrictModel):
    experience: ExperienceLevel
    studyField: str | None = Field(default=None, max_length=200)


class OnboardingStepRequest(StrictModel):
    answer: Any


class OnboardingProgress(BaseModel):
    current_step: int = Field(ge=1, le=12)
    completed_steps: list[int]
    completed: bool
    last_updated_at: datetime | None = None


class IndividualProfileResponse(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    updated_at: datetime | None = None
    onboarding: OnboardingProgress
    profile: dict[str, Any]
    answers: dict[str, Any]


class OnboardingStepResponse(BaseModel):
    saved: bool = True
    step: int = Field(ge=1, le=12)
    onboarding: OnboardingProgress
    profile: dict[str, Any]


class RoleOnboardingStepRequest(StrictModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer: Any


class RoleOnboardingProfileResponse(BaseModel):
    uid: str
    user_type: str
    answers: dict[str, Any]
    profile: dict[str, Any] = Field(default_factory=dict)
    onboarding_schema_version: int = 1
    onboarding: OnboardingProgress
