from datetime import date, time
from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: str | None = None
    dry_run: bool = False


class ChatResponse(BaseModel):
    session_id: str
    response: str
    trace: list[dict[str, Any]] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class SessionResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]
    clinical_summary: str | None = None


class AppointmentRequest(BaseModel):
    session_id: str
    doctor_id: int = Field(gt=0)
    appointment_date: date
    appointment_time: time
    confirmed_by_user: bool = False


class AppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    message: str


class StreamEvent(BaseModel):
    session_id: str
    event: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)