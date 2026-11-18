<<<<<<< HEAD
# advance_project_management_system
frontennd and backend
=======
# Project & Team Management System

React (Vite) dashboard + FastAPI REST API + MySQL.

## Structure
```
project-team-management/
├── backend/
│   ├── app/        main.py (routes, error handling, startup) · models.py · schemas.py
│   │               database.py · security.py (JWT, bcrypt, RBAC) · config.py
│   ├── migrations/ 001_initial_schema.sql
│   ├── tests/      pytest API tests
│   └── requirements.txt
├── frontend/       React + Vite  (src/App.jsx, api.js, main.jsx, style.css)
├── docs/           ER-DIAGRAM.md · API-ENDPOINTS.md
├── .env.example
└── README.md
```

## Setup
### 1. Database
```sql
CREATE DATABASE pm_system CHARACTER SET utf8mb4;
```
Tables are created automatically on first start. To create them manually, run `backend/migrations/001_initial_schema.sql`.

### 2. Backend
```bash
cp .env.example backend/.env        # edit DB credentials and SECRET_KEY
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Swagger: http://localhost:8000/docs · Default admin: `admin@example.com` / `Admin@12345` (change it).

### 3. Frontend
```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173
```
Backend URL defaults to `http://localhost:8000`; override with `VITE_API_URL` in `frontend/.env`.
If the frontend runs on another port, add its origin to `CORS_ORIGINS` in `backend/.env`.

### Assigning tasks
Only Admin can create projects, assign users to projects, create tasks, assign tasks, and manage task details. When creating a project, Admin selects which active users should see it; existing project membership can be changed from the project’s **Members** panel. Registering an account does not grant access to any project. Admin must explicitly assign the user to each project they should see.

Users can see only projects assigned to them and only tasks assigned to them within those projects. They can update the status and comment on their own assigned tasks. Existing automatically added project memberships are removed during startup, and tasks assigned through those old automatic memberships are made unassigned so the Admin can choose access explicitly.

### Tests
```bash
cd backend && pytest -q             # uses a temporary SQLite file
```

## Features
JWT auth with bcrypt, roles (Admin / Project Manager / Team Member), user management, projects with members and progress, tasks with priority/status/deadline/comments, activity logs, dashboard stats, search, filters, sorting, pagination, Kanban drag & drop, validation and exception handling, logging (console + `app.log`), Swagger/OpenAPI.

## Permissions
| Action | Admin | Project Manager | Team Member |
|---|---|---|---|
| Manage users and roles | yes | no | no |
| Create projects and assign project users | yes | no | no |
| View projects | all | assigned only | assigned only |
| Edit project / members | all | no | no |
| Delete project | all | no | no |
| Create / assign / edit / delete tasks | all | no | no |
| View tasks | all | own assigned tasks | own assigned tasks |
| Change task status / comment | all | own assigned tasks | own assigned tasks |
>>>>>>> 03c5938 (Initial commit)
