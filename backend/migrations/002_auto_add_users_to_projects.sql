ALTER TABLE project_members
  ADD COLUMN is_auto_added BOOLEAN NOT NULL DEFAULT FALSE;

INSERT IGNORE INTO project_members (project_id, user_id, is_auto_added)
SELECT p.id, u.id, TRUE
FROM projects AS p
CROSS JOIN users AS u
WHERE u.is_active = 1;
