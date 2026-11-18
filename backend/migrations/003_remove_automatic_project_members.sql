UPDATE tasks
SET assignee_id = NULL
WHERE EXISTS (
  SELECT 1
  FROM project_members
  WHERE project_members.project_id = tasks.project_id
    AND project_members.user_id = tasks.assignee_id
    AND project_members.is_auto_added = TRUE
);

DELETE FROM project_members
WHERE is_auto_added = TRUE;
