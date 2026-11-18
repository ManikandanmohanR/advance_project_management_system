import re
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import ProjectStatus, RoleName, TaskPriority, TaskStatus

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def _check_password(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must be at least 8 characters and contain a letter and a digit")
    return v


# ---------- Users / Auth ----------
class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: str = Field(validation_alias="role_name")


class UserOut(UserBrief):
    phone: str | None = None
    is_active: bool
    created_at: datetime


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    phone: str | None = Field(default=None, max_length=30)
    _pw = field_validator("password")(_check_password)


class UserCreate(RegisterIn):
    role: RoleName = RoleName.TEAM_MEMBER
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    password: str | None = None
    role: RoleName | None = None          # admin only
    is_active: bool | None = None         # admin only

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        return _check_password(v) if v is not None else v


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Projects ----------
class ProjectBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.PLANNING
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ProjectCreate(ProjectBase):
    member_ids: list[int] = []


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None


class MemberAdd(BaseModel):
    user_id: int


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    created_by: int
    creator_name: str
    created_at: datetime
    members: list[UserBrief]
    task_count: int
    completed_count: int
    progress: float


class ProjectStats(BaseModel):
    project_id: int
    total_tasks: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    overdue: int
    progress: float


# ---------- Tasks ----------
class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    project_id: int
    assignee_id: int | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    deadline: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    assignee_id: int | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    deadline: date | None = None


class StatusUpdate(BaseModel):
    status: TaskStatus


class TaskOut(BaseModel):
    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    deadline: date | None
    project_id: int
    project_name: str
    assignee_id: int | None
    assignee_name: str | None
    created_by: int
    creator_name: str
    updated_by: int | None
    updater_name: str | None
    created_at: datetime
    updated_at: datetime
    comment_count: int
    is_overdue: bool


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: int
    task_id: int
    user_id: int
    user_name: str
    content: str
    created_at: datetime


class ActivityOut(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None
    action: str
    details: str | None
    project_id: int | None
    task_id: int | None
    created_at: datetime


class DashboardOut(BaseModel):
    total_projects: int
    total_tasks: int
    completed: int
    pending: int            # To Do + Review
    in_progress: int
    overdue: int
    completion_rate: float
    by_status: dict[str, int]
    by_priority: dict[str, int]
    recent_activities: list[ActivityOut]
