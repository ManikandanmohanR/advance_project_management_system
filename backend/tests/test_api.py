from datetime import date, timedelta

from tests.conftest import login

B = "/api/v1"


def test_register_login_and_me(client):
    r = client.post(f"{B}/auth/register", json={"full_name": "Tom Member", "email": "tom@x.com", "password": "Passw0rdd"})
    assert r.status_code == 201 and r.json()["role"] == "Team Member"
    assert client.post(f"{B}/auth/register", json={"full_name": "Tom", "email": "tom@x.com", "password": "Passw0rdd"}).status_code == 409
    assert client.post(f"{B}/auth/register", json={"full_name": "Weak", "email": "w@x.com", "password": "short"}).status_code == 422
    h = login(client, "tom@x.com", "Passw0rdd")
    assert client.get(f"{B}/auth/me", headers=h).json()["email"] == "tom@x.com"
    assert client.get(f"{B}/auth/me").status_code == 401


def test_rbac_member_cannot_create_project(client):
    h = login(client, "tom@x.com", "Passw0rdd")
    assert client.post(f"{B}/projects", json={"name": "Nope"}, headers=h).status_code == 403
    assert client.post(f"{B}/users", json={"full_name": "x y", "email": "a@b.com", "password": "Passw0rdd"}, headers=h).status_code == 403


def test_project_task_flow(client, admin_h):
    users = client.get(f"{B}/users", headers=admin_h).json()["items"]
    tom = next(u for u in users if u["email"] == "tom@x.com")
    p = client.post(f"{B}/projects", headers=admin_h, json={
        "name": "Website", "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=30)), "member_ids": [tom["id"]]})
    assert p.status_code == 201, p.text
    pid = p.json()["id"]

    # invalid deadlines
    bad = {"title": "Task A", "project_id": pid, "deadline": str(date.today() - timedelta(days=1))}
    assert client.post(f"{B}/tasks", json=bad, headers=admin_h).status_code == 422
    bad["deadline"] = str(date.today() + timedelta(days=90))
    assert client.post(f"{B}/tasks", json=bad, headers=admin_h).status_code == 422

    t = client.post(f"{B}/tasks", headers=admin_h, json={
        "title": "Build header", "project_id": pid, "assignee_id": tom["id"],
        "priority": "High", "deadline": str(date.today() + timedelta(days=5))})
    assert t.status_code == 201, t.text
    tid = t.json()["id"]

    tom_h = login(client, "tom@x.com", "Passw0rdd")
    assert client.get(f"{B}/tasks/my", headers=tom_h).json()["total"] == 1
    # member can change status but not priority
    assert client.patch(f"{B}/tasks/{tid}/status", json={"status": "In Progress"}, headers=tom_h).status_code == 200
    assert client.put(f"{B}/tasks/{tid}", json={"priority": "Low"}, headers=tom_h).status_code == 403
    assert client.post(f"{B}/tasks/{tid}/comments", json={"content": "On it"}, headers=tom_h).status_code == 201

    client.patch(f"{B}/tasks/{tid}/status", json={"status": "Completed"}, headers=tom_h)
    stats = client.get(f"{B}/projects/{pid}/stats", headers=admin_h).json()
    assert stats["progress"] == 100.0
    dash = client.get(f"{B}/dashboard/stats", headers=admin_h).json()
    assert dash["total_tasks"] >= 1 and dash["recent_activities"]
    flt = client.get(f"{B}/tasks", params={"status": "Completed", "priority": "High", "q": "header"}, headers=admin_h).json()
    assert flt["total"] == 1
    assert len(client.get(f"{B}/tasks/{tid}/activity", headers=admin_h).json()) >= 3
    assert client.delete(f"{B}/tasks/{tid}", headers=admin_h).status_code == 204
    assert client.delete(f"{B}/projects/{pid}", headers=admin_h).status_code == 204


def test_task_assignment_requires_project_membership(client, admin_h):
    user = client.post(f"{B}/users", headers=admin_h, json={
        "full_name": "Assignment Target", "email": "assignment-target@x.com",
        "password": "Passw0rdd"})
    assert user.status_code == 201, user.text
    user_id = user.json()["id"]

    project = client.post(f"{B}/projects", headers=admin_h, json={"name": "Assignment project"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    task = {"title": "Assigned task", "project_id": project_id, "assignee_id": user_id}

    assert user_id not in {member["id"] for member in project.json()["members"]}
    rejected = client.post(f"{B}/tasks", headers=admin_h, json=task)
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "Assignee must be a member of the project"

    added = client.post(f"{B}/projects/{project_id}/members", headers=admin_h,
                        json={"user_id": user_id})
    assert added.status_code == 200, added.text
    assigned = client.post(f"{B}/tasks", headers=admin_h, json=task)
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["assignee_id"] == user_id


def test_new_registrant_sees_only_admin_assigned_projects(client, admin_h):
    project = client.post(f"{B}/projects", headers=admin_h, json={"name": "Shared project"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    registered = client.post(f"{B}/auth/register", json={
        "full_name": "New Teammate", "email": "new-teammate@x.com", "password": "Passw0rdd"})
    assert registered.status_code == 201, registered.text
    user_id = registered.json()["id"]
    user_h = login(client, "new-teammate@x.com", "Passw0rdd")

    projects = client.get(f"{B}/projects", headers=user_h).json()["items"]
    assert project_id not in {p["id"] for p in projects}
    assert client.get(f"{B}/projects/{project_id}", headers=user_h).status_code == 403
    assert client.post(f"{B}/projects", headers=user_h, json={"name": "Forbidden"}).status_code == 403
    assert client.get(f"{B}/users", headers=user_h).status_code == 403

    assigned_project = client.post(
        f"{B}/projects/{project_id}/members", headers=admin_h, json={"user_id": user_id})
    assert assigned_project.status_code == 200, assigned_project.text
    projects = client.get(f"{B}/projects", headers=user_h).json()["items"]
    assert project_id in {p["id"] for p in projects}
    details = client.get(f"{B}/projects/{project_id}", headers=user_h).json()
    assert user_id in {member["id"] for member in details["members"]}

    task = client.post(f"{B}/tasks", headers=admin_h, json={
        "title": "Welcome task", "project_id": project_id, "assignee_id": user_id})
    assert task.status_code == 201, task.text
    own_task_id = task.json()["id"]

    other_user = client.post(f"{B}/users", headers=admin_h, json={
        "full_name": "Other Teammate", "email": "other-teammate@x.com", "password": "Passw0rdd"})
    assert other_user.status_code == 201, other_user.text
    other_user_id = other_user.json()["id"]
    assert client.post(f"{B}/projects/{project_id}/members", headers=admin_h,
                       json={"user_id": other_user_id}).status_code == 200
    other_task = client.post(f"{B}/tasks", headers=admin_h, json={
        "title": "Other teammate task", "project_id": project_id, "assignee_id": other_user_id})
    assert other_task.status_code == 201, other_task.text

    other_project = client.post(f"{B}/projects", headers=admin_h, json={
        "name": "Other teammate project", "member_ids": [other_user_id]})
    assert other_project.status_code == 201, other_project.text
    other_project_task = client.post(f"{B}/tasks", headers=admin_h, json={
        "title": "Other project task", "project_id": other_project.json()["id"],
        "assignee_id": other_user_id})
    assert other_project_task.status_code == 201, other_project_task.text

    visible_project_ids = {p["id"] for p in client.get(f"{B}/projects", headers=user_h).json()["items"]}
    assert visible_project_ids == {project_id}
    admin_project_ids = {p["id"] for p in client.get(f"{B}/projects", headers=admin_h).json()["items"]}
    assert {project_id, other_project.json()["id"]}.issubset(admin_project_ids)
    assert client.get(f"{B}/tasks/my", headers=user_h).json()["total"] == 1
    assert client.get(f"{B}/tasks", headers=user_h).json()["total"] == 1
    assert client.get(f"{B}/tasks", headers=user_h, params={"assignee_id": other_user_id}).json()["total"] == 0
    assert client.get(f"{B}/tasks/{other_task.json()['id']}", headers=user_h).status_code == 403
    assert client.get(f"{B}/projects/{project_id}/stats", headers=user_h).json()["total_tasks"] == 1
    assert client.put(f"{B}/tasks/{own_task_id}", headers=user_h, json={
        "assignee_id": other_user_id}).status_code == 403
    assert client.post(f"{B}/tasks", headers=user_h, json={
        "title": "Forbidden task", "project_id": project_id, "assignee_id": user_id,
    }).status_code == 403


def test_project_manager_has_no_admin_project_or_task_controls(client, admin_h):
    manager = client.post(f"{B}/users", headers=admin_h, json={
        "full_name": "Shared Manager", "email": "shared-manager@x.com",
        "password": "Passw0rdd", "role": "Project Manager"})
    assert manager.status_code == 201, manager.text
    manager_id = manager.json()["id"]
    project = client.post(f"{B}/projects", headers=admin_h, json={"name": "Admin-owned project"})
    assert project.status_code == 201, project.text

    manager_h = login(client, "shared-manager@x.com", "Passw0rdd")
    assert client.post(f"{B}/projects", headers=manager_h, json={"name": "Forbidden"}).status_code == 403
    assert client.post(f"{B}/projects/{project.json()['id']}/members",
                       headers=manager_h, json={"user_id": manager_id}).status_code == 403
