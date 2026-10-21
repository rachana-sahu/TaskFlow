from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    timezone: str = "Asia/Kolkata"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    timezone: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    due_at: datetime
    remind_before_minutes: int = Field(default=60, ge=0, le=10080)
    track_id: str | None = None
    priority: str = "normal"
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in {"low", "normal", "high"}:
            raise ValueError("priority must be low, normal, or high")
        return value

    @field_validator("due_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at must include a timezone offset")
        return value.astimezone(UTC)


class TaskResponse(BaseModel):
    id: str
    track_id: str | None
    title: str
    due_at: datetime
    status: str
    priority: str
    estimated_duration_minutes: int | None
    notes: str | None
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("due_at", "completed_at", mode="before")
    @classmethod
    def normalize_due_at(cls, value):
        return _normalize_datetime(value)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    track_id: str | None = None
    status: str | None = None
    priority: str | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {
            "pending",
            "in_progress",
            "completed",
            "blocked",
            "archived",
        }:
            raise ValueError("Unsupported task status")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str | None) -> str | None:
        if value is not None and value not in {"low", "normal", "high"}:
            raise ValueError("priority must be low, normal, or high")
        return value


class TrackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class TrackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class TrackResponse(BaseModel):
    id: str
    name: str
    description: str
    sort_order: int
    archived_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("archived_at", "created_at", mode="before")
    @classmethod
    def normalize_dates(cls, value):
        return _normalize_datetime(value)


class TaskHistoryResponse(BaseModel):
    id: str
    event_type: str
    previous_status: str | None
    new_status: str | None
    details: str | None
    occurred_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("occurred_at", mode="before")
    @classmethod
    def normalize_occurred_at(cls, value):
        return _normalize_datetime(value)


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    body: str
    related_resource_type: str | None
    related_resource_id: str | None
    scheduled_at: datetime
    created_at: datetime
    read_at: datetime | None
    status: str
    model_config = ConfigDict(from_attributes=True)

    @field_validator("scheduled_at", "created_at", "read_at", mode="before")
    @classmethod
    def normalize_dates(cls, value):
        return _normalize_datetime(value)


class JobResponse(BaseModel):
    id: str
    task_type: str
    status: str
    attempt_count: int
    max_attempts: int
    scheduled_at: datetime
    completed_at: datetime | None
    error_message: str | None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("scheduled_at", "completed_at", mode="before")
    @classmethod
    def normalize_dates(cls, value):
        return _normalize_datetime(value)
