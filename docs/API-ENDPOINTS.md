# API Endpoints

Base URL: `http://localhost:8000/api/v1` · Interactive docs: `/docs` (Swagger) and `/redoc` · OpenAPI JSON: `/openapi.json` (import into Postman).
Authenticate with `Authorization: Bearer <token>` from `POST /auth/login`.

Roles: **A** Admin, **PM** Project Manager, **TM** Team Member.

## Auth
| Method | Path | Access | Description |
|---|---|---|---|
| POST | /auth/register | public | Register (always Team Member); no project access until Admin assigns projects |
| POST | /auth/login | public | Form fields `username` (email) + `password`; returns JWT + user |
| GET | /auth/me | any | Current user |

## Users
| Method | Path | Access | Description |
|---|---|---|---|
| GET | /users | A | List (q, role, is_active, page, page_size) |
| POST | /users | A | Create user with role |
| GET | /users/roles | A | List roles |
| PUT | /users/me | any | Update own name, phone, password |
| GET | /users/{id} | A, self | Get user |
| PUT | /users/{id} | A | Update profile, role, active flag, password |
| PATCH | /users/{id}/active?is_active= | A | Activate / deactivate |

## Projects
| Method | Path | Access | Description |
|---|---|---|---|
| GET | /projects | A: all; other users: assigned projects | q, status, sort_by, order, page, page_size |
| POST | /projects | A | Create with optional `member_ids` to assign active users |
| GET | /projects/{id} | A, assigned user | Details + progress; user task counts include only their assigned tasks |
| PUT | /projects/{id} | A | Update |
| DELETE | /projects/{id} | A | Delete with tasks |
| POST | /projects/{id}/members | A | Body `{user_id}`; explicitly assigns a user to the project |
| DELETE | /projects/{id}/members/{user_id} | A | Remove member and unassign their tasks in the project |
| GET | /projects/{id}/stats | A, assigned user | Admin sees all tasks; users see only their assigned task counts |

## Tasks
| Method | Path | Access | Description |
|---|---|---|---|
| GET | /tasks | A: all; other users: own assigned tasks | q, status, priority, project_id, assignee_id, overdue, sort_by (created_at, deadline, priority, title, updated_at), order, page, page_size |
| GET | /tasks/my | any | Tasks assigned to the logged-in user |
| POST | /tasks | A | Deadline cannot be in the past or outside project dates; assignee must be an active project member |
| GET | /tasks/{id} | A, assignee | Details |
| PUT | /tasks/{id} | A; assignee (status only) | Update |
| PATCH | /tasks/{id}/status | A, assignee | Body `{status}` |
| DELETE | /tasks/{id} | A | Delete |
| GET / POST | /tasks/{id}/comments | A, assignee | List / add comment |
| GET | /tasks/{id}/activity | A, assignee | Task history |

## Dashboard & activity
| Method | Path | Access | Description |
|---|---|---|---|
| GET | /dashboard/stats | any | Admin sees all; users see counts for their assigned projects and tasks |
| GET | /activities | any | Admin sees all; users see their own activity and history for assigned tasks; project_id, task_id, page, page_size |

## Errors
JSON `{"detail": "..."}`; validation errors (422) also include `errors: [{field, message}]`.
Codes: 400 bad request · 401 unauthenticated · 403 forbidden · 404 not found · 409 conflict · 422 validation · 500 server error.
Paginated responses: `{items, total, page, page_size, pages}`.
