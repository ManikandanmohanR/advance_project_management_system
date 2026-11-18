# ER Diagram

```mermaid
erDiagram
  ROLES ||--o{ USERS : "has"
  USERS ||--o{ PROJECTS : "creates"
  PROJECTS ||--o{ PROJECT_MEMBERS : "has"
  USERS ||--o{ PROJECT_MEMBERS : "joins"
  PROJECTS ||--o{ TASKS : "contains"
  USERS ||--o{ TASKS : "assigned / created / updated"
  TASKS ||--o{ TASK_COMMENTS : "has"
  USERS ||--o{ TASK_COMMENTS : "writes"
  USERS ||--o{ ACTIVITY_LOGS : "performs"

  ROLES { int id PK
          string name UK
          string description }
  USERS { int id PK
          string full_name
          string email UK
          string hashed_password
          string phone
          bool is_active
          int role_id FK
          datetime created_at }
  PROJECTS { int id PK
             string name
             text description
             enum status
             date start_date
             date end_date
             int created_by FK
             datetime created_at }
  PROJECT_MEMBERS { int id PK
                    int project_id FK
                    int user_id FK
                    bool is_auto_added
                    datetime joined_at }
  TASKS { int id PK
          string title
          text description
          enum status
          enum priority
          date deadline
          int project_id FK
          int assignee_id FK
          int created_by FK
          int updated_by FK
          datetime created_at
          datetime updated_at }
  TASK_COMMENTS { int id PK
                  int task_id FK
                  int user_id FK
                  text content
                  datetime created_at }
  ACTIVITY_LOGS { int id PK
                  int user_id FK
                  int project_id
                  int task_id
                  string action
                  string details
                  datetime created_at }
```

Notes
- `project_members` has a unique key on (`project_id`, `user_id`).
- Membership is assigned explicitly by an Admin. Existing rows marked `is_auto_added` from earlier versions are removed by migration `003_remove_automatic_project_members.sql`; tasks relying on those automatic memberships are unassigned (also handled automatically at startup).
- Deleting a project cascades to its members, tasks and comments.
- Deleting a user sets `tasks.assignee_id` and `activity_logs.user_id` to NULL.
- Enums: task status (To Do, In Progress, Review, Completed), priority (Low, Medium, High, Critical), project status (Planning, Active, On Hold, Completed).
- Plain SQL for MySQL: `backend/migrations/001_initial_schema.sql`.
