"""Project & Team Management API: app setup, routes, error handling."""
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import case, func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import (ActivityLog, Project, ProjectMember, ProjectStatus, Role, RoleName, Task,
                        TaskComment, TaskPriority, TaskStatus, User)
from app.schemas import (ActivityOut, CommentCreate, CommentOut, DashboardOut, MemberAdd, Page,
                         ProjectCreate, ProjectOut, ProjectStats, ProjectUpdate, RegisterIn,
                         StatusUpdate, TaskCreate, TaskOut, TaskUpdate, TokenOut, UserCreate,
                         UserOut, UserUpdate)
from app.security import (create_access_token, get_current_user,
                          get_project_for_user, hash_password, is_admin, require_admin,
                          verify_password, visible_project_ids)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("app.log")],
)
logger = logging.getLogger("app")


# ===================== helpers =====================
def log_activity(db: Session, user_id: int | None, action: str, details: str = "",
                 project_id: int | None = None, task_id: int | None = None) -> None:
    """Adds an activity row to the current session (the caller commits)."""
    db.add(ActivityLog(user_id=user_id, action=action, details=details[:500],
                       project_id=project_id, task_id=task_id))


def paginate(db: Session, stmt, page: int, page_size: int):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return rows, total, max(1, ceil(total / page_size))


def page_response(items, total, page, page_size, pages):
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


# ===================== AUTH ROUTES =====================

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Public self-registration. New accounts always get the Team Member role."""
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    role = db.scalar(select(Role).where(Role.name == RoleName.TEAM_MEMBER.value))
    user = User(full_name=data.full_name, email=data.email.lower(), phone=data.phone,
                hashed_password=hash_password(data.password), role_id=role.id)
    db.add(user)
    db.flush()
    log_activity(db, user.id, "user_registered", f"{user.full_name} registered")
    db.commit()
    db.refresh(user)
    return user


@auth_router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow: `username` is the email address."""
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.hashed_password):
        logger.warning("Failed login for %s", form.username)
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(403, "Account is deactivated")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user}


@auth_router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ===================== USERS ROUTES =====================

users_router = APIRouter(prefix="/users", tags=["Users"])


def _role(db: Session, name: RoleName) -> Role:
    return db.scalar(select(Role).where(Role.name == name.value))


@users_router.get("/roles", response_model=list[dict])
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"id": r.id, "name": r.name, "description": r.description} for r in db.scalars(select(Role))]


@users_router.get("", response_model=Page[UserOut])
def list_users(q: str | None = None, role: RoleName | None = None, is_active: bool | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), _: User = Depends(require_admin)):
    stmt = select(User).order_by(User.full_name)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.full_name.like(like), User.email.like(like)))
    if role:
        stmt = stmt.join(Role).where(Role.name == role.value)
    rows, total, pages = paginate(db, stmt, page, page_size)
    return page_response(rows, total, page, page_size, pages)


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(full_name=data.full_name, email=data.email.lower(), phone=data.phone,
             hashed_password=hash_password(data.password), is_active=data.is_active,
             role_id=_role(db, data.role).id)
    db.add(u)
    db.flush()
    log_activity(db, admin.id, "user_created", f"Created user {u.full_name} ({data.role.value})")
    db.commit()
    db.refresh(u)
    return u


@users_router.put("/me", response_model=UserOut)
def update_me(data: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Update own profile (name, phone, password). Role/active changes are ignored here."""
    if data.full_name:
        user.full_name = data.full_name
    if data.phone is not None:
        user.phone = data.phone
    if data.password:
        user.hashed_password = hash_password(data.password)
    log_activity(db, user.id, "profile_updated", f"{user.full_name} updated their profile")
    db.commit()
    db.refresh(user)
    return user


@users_router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not is_admin(user) and user_id != user.id:
        raise HTTPException(403, "You can only view your own user profile")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


@users_router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id and (data.is_active is False or (data.role and data.role != RoleName.ADMIN)):
        raise HTTPException(400, "You cannot deactivate or demote your own account")
    if data.full_name:
        u.full_name = data.full_name
    if data.phone is not None:
        u.phone = data.phone
    if data.password:
        u.hashed_password = hash_password(data.password)
    if data.role:
        u.role_id = _role(db, data.role).id
    if data.is_active is not None:
        u.is_active = data.is_active
    log_activity(db, admin.id, "user_updated", f"Updated user {u.full_name}")
    db.commit()
    db.refresh(u)
    return u


@users_router.patch("/{user_id}/active", response_model=UserOut)
def set_active(user_id: int, is_active: bool, db: Session = Depends(get_db),
               admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    u.is_active = is_active
    log_activity(db, admin.id, "user_activated" if is_active else "user_deactivated", u.full_name)
    db.commit()
    db.refresh(u)
    return u


# ===================== PROJECTS ROUTES =====================

projects_router = APIRouter(prefix="/projects", tags=["Projects"])


def _counts(db: Session, ids: list[int], user: User) -> dict[int, tuple[int, int]]:
    if not ids:
        return {}
    done = func.coalesce(func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)), 0)
    stmt = select(Task.project_id, func.count(Task.id), done).where(Task.project_id.in_(ids))
    if not is_admin(user):
        stmt = stmt.where(Task.assignee_id == user.id)
    rows = db.execute(stmt.group_by(Task.project_id)).all()
    return {r[0]: (int(r[1]), int(r[2])) for r in rows}


def project_out(p: Project, counts: dict) -> dict:
    total, done = counts.get(p.id, (0, 0))
    return {
        "id": p.id, "name": p.name, "description": p.description, "status": p.status,
        "start_date": p.start_date, "end_date": p.end_date, "created_by": p.created_by,
        "creator_name": p.creator.full_name, "created_at": p.created_at,
        "members": [m.user for m in p.members], "task_count": total, "completed_count": done,
        "progress": round(done / total * 100, 1) if total else 0.0,
    }


@projects_router.get("", response_model=Page[ProjectOut])
def list_projects(q: str | None = None, status: ProjectStatus | None = None,
                  sort_by: str = Query("created_at", pattern="^(created_at|start_date|end_date|name)$"),
                  order: str = Query("desc", pattern="^(asc|desc)$"),
                  page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Project)
    vis = visible_project_ids(user)
    if vis is not None:
        stmt = stmt.where(Project.id.in_(vis))
    if q:
        stmt = stmt.where(Project.name.like(f"%{q}%") | Project.description.like(f"%{q}%"))
    if status:
        stmt = stmt.where(Project.status == status)
    col = getattr(Project, sort_by)
    stmt = stmt.order_by(col.asc() if order == "asc" else col.desc(), Project.id.desc())
    rows, total, pages = paginate(db, stmt, page, page_size)
    counts = _counts(db, [p.id for p in rows], user)
    return page_response([project_out(p, counts) for p in rows], total, page, page_size, pages)


@projects_router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    member_ids = set(data.member_ids)
    found = set(db.scalars(select(User.id).where(
        User.id.in_(member_ids), User.is_active.is_(True)
    ))) if member_ids else set()
    if found != member_ids:
        raise HTTPException(400, "One or more member ids are invalid or inactive")
    p = Project(**data.model_dump(exclude={"member_ids"}), created_by=user.id)
    p.members = [ProjectMember(user_id=uid) for uid in member_ids]
    db.add(p)
    db.flush()
    log_activity(db, user.id, "project_created", f"Created project '{p.name}'", project_id=p.id)
    db.commit()
    db.refresh(p)
    return project_out(p, _counts(db, [p.id], user))


@projects_router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = get_project_for_user(db, project_id, user)
    return project_out(p, _counts(db, [p.id], user))


@projects_router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_admin)):
    p = get_project_for_user(db, project_id, user)
    changes = data.model_dump(exclude_unset=True)
    start = changes.get("start_date", p.start_date)
    end = changes.get("end_date", p.end_date)
    if start and end and end < start:
        raise HTTPException(422, "end_date cannot be before start_date")
    for k, v in changes.items():
        setattr(p, k, v)
    log_activity(db, user.id, "project_updated", f"Updated project '{p.name}': {', '.join(changes) or 'no changes'}",
                 project_id=p.id)
    db.commit()
    db.refresh(p)
    return project_out(p, _counts(db, [p.id], user))


@projects_router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    p = get_project_for_user(db, project_id, user)
    name = p.name
    db.delete(p)
    log_activity(db, user.id, "project_deleted", f"Deleted project '{name}'", project_id=project_id)
    db.commit()


@projects_router.post("/{project_id}/members", response_model=ProjectOut)
def add_member(project_id: int, data: MemberAdd, db: Session = Depends(get_db),
               user: User = Depends(require_admin)):
    p = get_project_for_user(db, project_id, user)
    target = db.get(User, data.user_id)
    if not target or not target.is_active:
        raise HTTPException(404, "User not found or inactive")
    if any(m.user_id == target.id for m in p.members):
        raise HTTPException(409, "User is already a member")
    p.members.append(ProjectMember(user_id=target.id))
    log_activity(db, user.id, "member_added", f"Added {target.full_name} to '{p.name}'", project_id=p.id)
    db.commit()
    db.refresh(p)
    return project_out(p, _counts(db, [p.id], user))


@projects_router.delete("/{project_id}/members/{user_id}", response_model=ProjectOut)
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db),
                  user: User = Depends(require_admin)):
    p = get_project_for_user(db, project_id, user)
    m = next((m for m in p.members if m.user_id == user_id), None)
    if not m:
        raise HTTPException(404, "User is not a member")
    # unassign their tasks in this project
    for t in db.scalars(select(Task).where(Task.project_id == p.id, Task.assignee_id == user_id)):
        t.assignee_id = None
    p.members.remove(m)
    log_activity(db, user.id, "member_removed", f"Removed {m.user.full_name} from '{p.name}'", project_id=p.id)
    db.commit()
    db.refresh(p)
    return project_out(p, _counts(db, [p.id], user))


@projects_router.get("/{project_id}/stats", response_model=ProjectStats)
def project_stats(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = get_project_for_user(db, project_id, user)
    task_stmt = select(Task).where(Task.project_id == p.id)
    if not is_admin(user):
        task_stmt = task_stmt.where(Task.assignee_id == user.id)
    tasks = db.scalars(task_stmt).unique().all()
    by_status = {s.value: 0 for s in TaskStatus}
    by_priority = {s.value: 0 for s in TaskPriority}
    overdue = 0
    for t in tasks:
        by_status[t.status.value] += 1
        by_priority[t.priority.value] += 1
        if t.deadline and t.deadline < date.today() and t.status != TaskStatus.COMPLETED:
            overdue += 1
    total = len(tasks)
    done = by_status[TaskStatus.COMPLETED.value]
    return {"project_id": p.id, "total_tasks": total, "by_status": by_status, "by_priority": by_priority,
            "overdue": overdue, "progress": round(done / total * 100, 1) if total else 0.0}


# ===================== TASKS ROUTES =====================

tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _comment_counts(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = db.execute(select(TaskComment.task_id, func.count(TaskComment.id))
                      .where(TaskComment.task_id.in_(ids)).group_by(TaskComment.task_id)).all()
    return {row[0]: row[1] for row in rows}


def task_out(t: Task, cc: dict) -> dict:
    return {
        "id": t.id, "title": t.title, "description": t.description, "status": t.status,
        "priority": t.priority, "deadline": t.deadline, "project_id": t.project_id,
        "project_name": t.project.name, "assignee_id": t.assignee_id,
        "assignee_name": t.assignee.full_name if t.assignee else None,
        "created_by": t.created_by, "creator_name": t.creator.full_name,
        "updated_by": t.updated_by, "updater_name": t.updater.full_name if t.updater else None,
        "created_at": t.created_at, "updated_at": t.updated_at, "comment_count": cc.get(t.id, 0),
        "is_overdue": bool(t.deadline and t.deadline < date.today() and t.status != TaskStatus.COMPLETED),
    }


def _validate_deadline(deadline: date | None, project: Project) -> None:
    if not deadline:
        return
    if deadline < date.today():
        raise HTTPException(422, "Deadline cannot be in the past")
    if project.start_date and deadline < project.start_date:
        raise HTTPException(422, "Deadline is before the project start date")
    if project.end_date and deadline > project.end_date:
        raise HTTPException(422, "Deadline is after the project end date")


def _validate_assignee(db: Session, assignee_id: int | None, project: Project) -> None:
    if assignee_id is None:
        return
    u = db.get(User, assignee_id)
    if not u or not u.is_active:
        raise HTTPException(404, "Assignee not found or inactive")
    if assignee_id not in {m.user_id for m in project.members}:
        raise HTTPException(400, "Assignee must be a member of the project")


def _get_task(db: Session, task_id: int, user: User) -> Task:
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    get_project_for_user(db, t.project_id, user)  # access check
    if not is_admin(user) and t.assignee_id != user.id:
        raise HTTPException(403, "You can only view tasks assigned to you")
    return t


def _list(db, user, *, mine=False, q=None, status=None, priority=None, project_id=None,
          assignee_id=None, overdue=False, sort_by="created_at", order="desc", page=1, page_size=10):
    stmt = select(Task)
    vis = visible_project_ids(user)
    if vis is not None:
        stmt = stmt.where(Task.project_id.in_(vis))
        stmt = stmt.where(Task.assignee_id == user.id)
    if mine:
        stmt = stmt.where(Task.assignee_id == user.id)
    if q:
        stmt = stmt.where(Task.title.like(f"%{q}%") | Task.description.like(f"%{q}%"))
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    if assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if overdue:
        stmt = stmt.where(Task.deadline < date.today(), Task.status != TaskStatus.COMPLETED)
    col = getattr(Task, sort_by)
    stmt = stmt.order_by(col.asc() if order == "asc" else col.desc(), Task.id.desc())
    rows, total, pages = paginate(db, stmt, page, page_size)
    cc = _comment_counts(db, [t.id for t in rows])
    return page_response([task_out(t, cc) for t in rows], total, page, page_size, pages)


_SORT = "^(created_at|deadline|priority|title|updated_at)$"
_ORDER = "^(asc|desc)$"


@tasks_router.get("", response_model=Page[TaskOut])
def list_tasks(q: str | None = None, status: TaskStatus | None = None, priority: TaskPriority | None = None,
               project_id: int | None = None, assignee_id: int | None = None, overdue: bool = False,
               sort_by: str = Query("created_at", pattern=_SORT), order: str = Query("desc", pattern=_ORDER),
               page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _list(db, user, q=q, status=status, priority=priority, project_id=project_id,
                 assignee_id=assignee_id, overdue=overdue, sort_by=sort_by, order=order,
                 page=page, page_size=page_size)


@tasks_router.get("/my", response_model=Page[TaskOut])
def my_tasks(q: str | None = None, status: TaskStatus | None = None, priority: TaskPriority | None = None,
             sort_by: str = Query("deadline", pattern=_SORT), order: str = Query("asc", pattern=_ORDER),
             page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Tasks assigned to the logged-in user."""
    return _list(db, user, mine=True, q=q, status=status, priority=priority,
                 sort_by=sort_by, order=order, page=page, page_size=page_size)


@tasks_router.post("", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    project = get_project_for_user(db, data.project_id, user)
    _validate_deadline(data.deadline, project)
    _validate_assignee(db, data.assignee_id, project)
    t = Task(**data.model_dump(), created_by=user.id, updated_by=user.id)
    db.add(t)
    db.flush()
    log_activity(db, user.id, "task_created", f"Created task '{t.title}'", project.id, t.id)
    if t.assignee_id:
        log_activity(db, user.id, "task_assigned", f"Assigned '{t.title}' to user #{t.assignee_id}", project.id, t.id)
    db.commit()
    db.refresh(t)
    return task_out(t, {})


@tasks_router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = _get_task(db, task_id, user)
    return task_out(t, _comment_counts(db, [t.id]))


@tasks_router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    t = _get_task(db, task_id, user)
    changes = data.model_dump(exclude_unset=True)
    if not is_admin(user):
        # Team members may only change the status of tasks assigned to them
        if t.assignee_id != user.id or set(changes) - {"status"}:
            raise HTTPException(403, "You can only update the status of tasks assigned to you")
    if "deadline" in changes and changes["deadline"] != t.deadline:
        _validate_deadline(changes["deadline"], t.project)
    if "assignee_id" in changes:
        _validate_assignee(db, changes["assignee_id"], t.project)
    for field, new in changes.items():
        old = getattr(t, field)
        if old == new:
            continue
        o, n = getattr(old, "value", old), getattr(new, "value", new)
        action = {"status": "status_changed", "assignee_id": "task_assigned",
                  "priority": "priority_changed"}.get(field, "task_updated")
        log_activity(db, user.id, action, f"'{t.title}': {field} {o} -> {n}", t.project_id, t.id)
        setattr(t, field, new)
    t.updated_by = user.id
    db.commit()
    db.refresh(t)
    return task_out(t, _comment_counts(db, [t.id]))


@tasks_router.patch("/{task_id}/status", response_model=TaskOut)
def update_status(task_id: int, data: StatusUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return update_task(task_id, TaskUpdate(status=data.status), db, user)


@tasks_router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    t = _get_task(db, task_id, user)
    log_activity(db, user.id, "task_deleted", f"Deleted task '{t.title}'", t.project_id, t.id)
    db.delete(t)
    db.commit()


@tasks_router.get("/{task_id}/comments", response_model=list[CommentOut])
def list_comments(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = _get_task(db, task_id, user)
    return [{"id": c.id, "task_id": c.task_id, "user_id": c.user_id, "user_name": c.user.full_name,
             "content": c.content, "created_at": c.created_at} for c in t.comments]


@tasks_router.post("/{task_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(task_id: int, data: CommentCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    t = _get_task(db, task_id, user)
    c = TaskComment(task_id=t.id, user_id=user.id, content=data.content.strip())
    db.add(c)
    log_activity(db, user.id, "comment_added", f"Commented on '{t.title}'", t.project_id, t.id)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "task_id": c.task_id, "user_id": c.user_id, "user_name": user.full_name,
            "content": c.content, "created_at": c.created_at}


@tasks_router.get("/{task_id}/activity", response_model=list[ActivityOut])
def task_activity(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = _get_task(db, task_id, user)
    rows = db.scalars(select(ActivityLog).where(ActivityLog.task_id == t.id)
                      .order_by(ActivityLog.id.desc()).limit(100)).unique().all()
    return [activity_out(a) for a in rows]


def activity_out(a: ActivityLog) -> dict:
    return {"id": a.id, "user_id": a.user_id, "user_name": a.user.full_name if a.user else None,
            "action": a.action, "details": a.details, "project_id": a.project_id,
            "task_id": a.task_id, "created_at": a.created_at}


# ===================== DASHBOARD ROUTES =====================

dashboard_router = APIRouter(tags=["Dashboard & Activity"])


def _scoped_activity(stmt, user: User):
    if is_admin(user):
        return stmt
    assigned_tasks = select(Task.id).where(Task.assignee_id == user.id)
    return stmt.where(or_(ActivityLog.task_id.in_(assigned_tasks), ActivityLog.user_id == user.id))


@dashboard_router.get("/dashboard/stats", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    vis = visible_project_ids(user)
    pstmt = select(func.count(Project.id))
    tstmt = select(Task)
    if vis is not None:
        pstmt = pstmt.where(Project.id.in_(vis))
        tstmt = tstmt.where(Task.project_id.in_(vis), Task.assignee_id == user.id)
    tasks = db.scalars(tstmt).unique().all()
    by_status = {s.value: 0 for s in TaskStatus}
    by_priority = {p.value: 0 for p in TaskPriority}
    overdue = 0
    for t in tasks:
        by_status[t.status.value] += 1
        by_priority[t.priority.value] += 1
        if t.deadline and t.deadline < date.today() and t.status != TaskStatus.COMPLETED:
            overdue += 1
    total = len(tasks)
    done = by_status["Completed"]
    recent = db.scalars(_scoped_activity(select(ActivityLog), user)
                        .order_by(ActivityLog.id.desc()).limit(10)).unique().all()
    return {
        "total_projects": db.scalar(pstmt) or 0, "total_tasks": total, "completed": done,
        "pending": by_status["To Do"] + by_status["Review"], "in_progress": by_status["In Progress"],
        "overdue": overdue, "completion_rate": round(done / total * 100, 1) if total else 0.0,
        "by_status": by_status, "by_priority": by_priority,
        "recent_activities": [activity_out(a) for a in recent],
    }


@dashboard_router.get("/activities", response_model=Page[ActivityOut])
def activities(project_id: int | None = None, task_id: int | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if project_id:
        get_project_for_user(db, project_id, user)
    if task_id:
        _get_task(db, task_id, user)
    stmt = _scoped_activity(select(ActivityLog), user).order_by(ActivityLog.id.desc())
    if project_id:
        stmt = stmt.where(ActivityLog.project_id == project_id)
    if task_id:
        stmt = stmt.where(ActivityLog.task_id == task_id)
    rows, total, pages = paginate(db, stmt, page, page_size)
    return page_response([activity_out(a) for a in rows], total, page, page_size, pages)


# ===================== APP SETUP =====================
ROLE_DESC = {
    RoleName.ADMIN: "Full access: users, roles, all projects and tasks",
    RoleName.PROJECT_MANAGER: "Views assigned projects and works on assigned tasks",
    RoleName.TEAM_MEMBER: "Views assigned projects and works on assigned tasks",
}


def seed() -> None:
    with SessionLocal() as db:
        for r in RoleName:
            if not db.scalar(select(Role).where(Role.name == r.value)):
                db.add(Role(name=r.value, description=ROLE_DESC[r]))
        db.commit()
        if not db.scalar(select(User).where(User.email == settings.FIRST_ADMIN_EMAIL.lower())):
            admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
            db.add(User(full_name=settings.FIRST_ADMIN_NAME, email=settings.FIRST_ADMIN_EMAIL.lower(),
                        hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD), role_id=admin_role.id))
            db.commit()
            logger.info("Seeded default admin %s", settings.FIRST_ADMIN_EMAIL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    member_columns = {column["name"] for column in inspect(engine).get_columns("project_members")}
    if "is_auto_added" not in member_columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE project_members ADD COLUMN is_auto_added BOOLEAN NOT NULL DEFAULT 0"
            ))
    with SessionLocal() as db:
        db.execute(text(
            "UPDATE tasks SET assignee_id = NULL "
            "WHERE EXISTS (SELECT 1 FROM project_members "
            "WHERE project_members.project_id = tasks.project_id "
            "AND project_members.user_id = tasks.assignee_id "
            "AND project_members.is_auto_added = TRUE)"
        ))
        db.query(ProjectMember).filter(ProjectMember.is_auto_added.is_(True)).delete(synchronize_session=False)
        db.commit()
    seed()
    logger.info("Application started")
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan,
              description="REST API for projects, tasks, teams, comments and activity tracking.",
              docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")

app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
                   allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(x) for x in e["loc"] if x != "body"), "message": e["msg"]}
              for e in exc.errors()]
    detail = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError):
    logger.warning("Integrity error: %s", exc.orig)
    return JSONResponse(status_code=409, content={"detail": "Operation conflicts with existing data"})


@app.exception_handler(SQLAlchemyError)
async def db_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Database error"})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


API = "/api/v1"
for r in (auth_router, users_router, projects_router, tasks_router, dashboard_router):
    app.include_router(r, prefix=API)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
