import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, listProjects, listUsers, qs, session } from './api';

const STATUSES = ['To Do', 'In Progress', 'Review', 'Completed'];
const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'];
const PSTATUS = ['Planning', 'Active', 'On Hold', 'Completed'];
const ROLES = ['Admin', 'Project Manager', 'Team Member'];
const STATUS_COLOR = { 'To Do': 'var(--mute)', 'In Progress': 'var(--accent)', Review: 'var(--warn)', Completed: 'var(--ok)' };
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const Ctx = createContext(null);
const useApp = () => useContext(Ctx);

/* ---------- helpers ---------- */
const fmtD = (d) => { if (!d) return '—'; const [y, m, dd] = d.split('-'); return `${dd} ${MONTHS[m - 1]} ${y}`; };
const ago = (ts) => {
  const s = (Date.now() - new Date(ts + 'Z')) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
};
const Badge = ({ t, k }) => <span className={`badge ${k}-${String(t).replace(/ /g, '-')}`}>{t}</span>;
const Options = ({ items, blank }) => (
  <>
    {blank != null && <option value="">{blank}</option>}
    {items.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return <option key={v} value={v}>{l}</option>; })}
  </>
);

function useData(loader, deps) {
  const { ver } = useApp();
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    loader()
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((e) => live && setState({ data: null, error: e.message, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, ver]);
  return state;
}

function SearchBox({ value, onChange, placeholder }) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => v !== value && onChange(v), 300); return () => clearTimeout(t); }, [v]); // eslint-disable-line
  return <input value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)} />;
}

const Pager = ({ m, onPage }) => (
  <div className="pager">
    <span className="sm mute">{m.total} result{m.total === 1 ? '' : 's'} · page {m.page} of {m.pages}</span>
    <button className="btn ghost xs" disabled={m.page <= 1} onClick={() => onPage(m.page - 1)}>Previous</button>
    <button className="btn ghost xs" disabled={m.page >= m.pages} onClick={() => onPage(m.page + 1)}>Next</button>
  </div>
);

const Modal = ({ children }) => {
  const { ui } = useApp();
  return (
    <div className="modalbg" onMouseDown={(e) => e.target === e.currentTarget && ui.close()}>
      <div className="modal" role="dialog">{children}</div>
    </div>
  );
};

const Page = ({ title, actions, children }) => (
  <>
    <div className="top"><h1>{title}</h1><div className="sp" />{actions}</div>
    {children}
  </>
);

const Activity = ({ a }) => (
  <div className="act"><b>{a.user_name || 'System'}</b> <span className="mute">{a.details || a.action}</span><div className="sm mute">{ago(a.created_at)}</div></div>
);

/* ---------- auth ---------- */
function Auth({ onLogin, toast }) {
  const [reg, setReg] = useState(false);
  const [f, setF] = useState({ name: '', email: '', password: '' });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      if (reg) await api('/auth/register', { method: 'POST', body: { full_name: f.name.trim(), email: f.email.trim(), password: f.password } });
      const d = await api('/auth/login', { method: 'POST', form: { username: f.email.trim(), password: f.password } });
      session.save(d.access_token, d.user);
      onLogin(d.user);
    } catch (err) { toast(err.message, true); }
  };
  return (
    <section id="auth">
      <div className="hero"><h1>Task board keeps every project moving.</h1><p>Plan projects, hand out tasks, and see where the work stands without chasing anyone for updates.</p></div>
      <div className="box">
        <form onSubmit={submit}>
          <h2>{reg ? 'Create account' : 'Sign in'}</h2>
          {reg && <label>Full name<input required value={f.name} onChange={set('name')} autoComplete="name" /></label>}
          <label>Email<input type="email" required value={f.email} onChange={set('email')} autoComplete="username" /></label>
          <label>Password<input type="password" required value={f.password} onChange={set('password')} autoComplete={reg ? 'new-password' : 'current-password'} /></label>
          <button className="btn">{reg ? 'Register' : 'Sign in'}</button>
          <button type="button" className="linkbtn sm" onClick={() => setReg(!reg)}>{reg ? 'Have an account? Sign in' : 'Need an account? Register'}</button>
          {reg && <span className="sm mute">New accounts start as Team Members. An admin can change roles. Use 8+ characters with a letter and a digit.</span>}
        </form>
      </div>
    </section>
  );
}

/* ---------- dashboard ---------- */
function Dashboard() {
  const { data: d, error } = useData(() => api('/dashboard/stats'), []);
  if (error) return <div className="card">{error}</div>;
  if (!d) return null;
  const tot = d.total_tasks || 1;
  const stat = (n, l, c = '') => <div className="card stat"><b className={c}>{n}</b><span className="mute">{l}</span></div>;
  return (
    <Page title="Dashboard">
      <div className="grid g4">
        {stat(d.total_projects, 'Projects')}{stat(d.total_tasks, 'Tasks')}{stat(d.completed, 'Completed')}
        {stat(d.in_progress, 'In progress')}{stat(d.pending, 'Pending (To Do + Review)')}{stat(d.overdue, 'Overdue', d.overdue ? 'late' : '')}
      </div>
      <div className="grid g2" style={{ marginTop: '1rem' }}>
        <div className="card">
          <h2>Completion</h2>
          <p className="mute sm">{d.completed} of {d.total_tasks} tasks done</p>
          <h1 style={{ fontSize: '2.4rem' }}>{d.completion_rate}%</h1>
          <div className="bar" style={{ margin: '.6rem 0 1.2rem' }}><i style={{ width: `${d.completion_rate}%` }} /></div>
          <div className="seg">{STATUSES.map((s) => <i key={s} style={{ width: `${(d.by_status[s] / tot) * 100}%`, background: STATUS_COLOR[s] }} />)}</div>
          <div className="row sm" style={{ marginTop: '.7rem' }}>{STATUSES.map((s) => <span key={s}><span style={{ color: STATUS_COLOR[s] }}>●</span> {s}: {d.by_status[s]}</span>)}</div>
        </div>
        <div className="card">
          <h2>Tasks by priority</h2>
          <div style={{ marginTop: '.8rem', display: 'grid', gap: '.6rem' }}>
            {PRIORITIES.map((p) => (
              <div key={p}>
                <div className="row sm"><span>{p}</span><span className="sp" /><span>{d.by_priority[p]}</span></div>
                <div className="bar"><i className={`p-${p}`} style={{ width: `${(d.by_priority[p] / tot) * 100}%`, background: 'currentColor' }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="card" style={{ marginTop: '1rem' }}>
        <h2>Recent activity</h2>
        {d.recent_activities.length ? d.recent_activities.map((a) => <Activity key={a.id} a={a} />) : <p className="mute">Nothing yet. Create a project to get started.</p>}
      </div>
    </Page>
  );
}

/* ---------- projects ---------- */
function Projects() {
  const { isAdmin, ui, run, refresh, toast, go } = useApp();
  const [f, setF] = useState({ q: '', status: '', page: 1 });
  const { data: d } = useData(() => api('/projects?' + qs({ ...f, page_size: 8 })), [f]);
  const del = (p) => ui.open('confirm', {
    msg: `Delete "${p.name}" and all of its tasks?`,
    onYes: () => run(async () => { await api(`/projects/${p.id}`, { method: 'DELETE' }); toast('Project deleted'); refresh(); }),
  });
  return (
    <Page title="Projects" actions={isAdmin && <button className="btn" onClick={() => ui.open('projectForm')}>New project</button>}>
      <div className="filters">
        <SearchBox value={f.q} placeholder="Search projects" onChange={(q) => setF({ ...f, q, page: 1 })} />
        <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value, page: 1 })}><Options items={PSTATUS} blank="All statuses" /></select>
      </div>
      {d && (
        <>
          <div className="grid g2">
            {d.items.map((p) => (
              <div className="card" key={p.id}>
                <div className="row"><h3><button className="linkbtn" onClick={() => go('project', p.id)}>{p.name}</button></h3><span className="sp" /><Badge t={p.status} k="s" /></div>
                <p className="mute sm" style={{ minHeight: '2.6em' }}>{(p.description || 'No description').slice(0, 110)}</p>
                <div className="bar"><i style={{ width: `${p.progress}%` }} /></div>
                <div className="row sm mute" style={{ marginTop: '.5rem' }}><span>{p.progress}% · {p.completed_count}/{p.task_count} tasks</span><span className="sp" /><span>{fmtD(p.start_date)} to {fmtD(p.end_date)}</span></div>
                <div className="row sm mute" style={{ marginTop: '.4rem' }}>
                  {p.members.length} member{p.members.length === 1 ? '' : 's'}<span className="sp" />
                  {isAdmin && <><button className="btn ghost xs" onClick={() => ui.open('projectForm', { project: p })}>Edit</button><button className="btn ghost xs" onClick={() => del(p)}>Delete</button></>}
                </div>
              </div>
            ))}
            {!d.items.length && <div className="card mute">No projects found.</div>}
          </div>
          <Pager m={d} onPage={(page) => setF({ ...f, page })} />
        </>
      )}
    </Page>
  );
}

function ProjectForm({ project }) {
  const { ui, run, toast, refresh } = useApp();
  const [f, setF] = useState({
    name: project?.name || '', description: project?.description || '', status: project?.status || 'Planning',
    start_date: project?.start_date || '', end_date: project?.end_date || '',
  });
  const [members, setMembers] = useState(new Set());
  const { data: users } = useData(() => (project ? Promise.resolve([]) : listUsers()), []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = () => run(async () => {
    const body = { ...f, name: f.name.trim(), start_date: f.start_date || null, end_date: f.end_date || null };
    if (project) await api(`/projects/${project.id}`, { method: 'PUT', body });
    else await api('/projects', { method: 'POST', body: { ...body, member_ids: [...members] } });
    ui.close(); toast('Project saved'); refresh();
  });
  const toggle = (id) => { const s = new Set(members); s.has(id) ? s.delete(id) : s.add(id); setMembers(s); };
  return (
    <Modal>
      <h2>{project ? 'Edit project' : 'New project'}</h2>
      <label>Name<input value={f.name} onChange={set('name')} /></label>
      <label>Description<textarea rows="3" value={f.description} onChange={set('description')} /></label>
      <div className="two">
        <label>Start date<input type="date" value={f.start_date} onChange={set('start_date')} /></label>
        <label>End date<input type="date" value={f.end_date} onChange={set('end_date')} /></label>
      </div>
      <label>Status<select value={f.status} onChange={set('status')}><Options items={PSTATUS} /></select></label>
      {project ? <p className="sm mute">Manage members from the project page.</p> : (
        <label>Assign users to this project
          <span className="sm mute">Only selected active users will be able to see this project.</span>
          <div className="members">
            {(users || []).filter((u) => u.is_active).map((u) => (
              <label className="chk" key={u.id}><input type="checkbox" checked={members.has(u.id)} onChange={() => toggle(u.id)} />{u.full_name} <span className="mute">({u.role})</span></label>
            ))}
          </div>
        </label>
      )}
      <div className="row"><div className="sp" /><button className="btn ghost" onClick={ui.close}>Cancel</button><button className="btn" onClick={save}>Save project</button></div>
    </Modal>
  );
}

function ProjectDetail({ id }) {
  const { user, ui, run, toast, refresh } = useApp();
  const { data, error } = useData(() => Promise.all([
    api(`/projects/${id}`), api(`/projects/${id}/stats`), api(`/activities?project_id=${id}&page_size=8`),
    api(`/tasks?project_id=${id}&page_size=100&sort_by=deadline&order=asc`),
    user.role === 'Admin' ? listUsers() : Promise.resolve([]),
  ]), [id, user.role]);
  const [sel, setSel] = useState('');
  if (error) return <div className="card">{error}</div>;
  if (!data) return null;
  const [p, st, acts, tasks, users] = data;
  const canEdit = user.role === 'Admin';
  const memberIds = new Set(p.members.map((m) => m.id));
  const candidates = users.filter((u) => u.is_active && !memberIds.has(u.id));
  const add = () => run(async () => {
    const uid = sel || candidates[0]?.id;
    if (!uid) return;
    await api(`/projects/${id}/members`, { method: 'POST', body: { user_id: +uid } }); toast('Member added'); setSel(''); refresh();
  });
  const remove = (m) => ui.open('confirm', {
    msg: `Remove ${m.full_name}? Their tasks in this project become unassigned.`,
    onYes: () => run(async () => { await api(`/projects/${id}/members/${m.id}`, { method: 'DELETE' }); refresh(); }),
  });
  return (
    <Page title={p.name} actions={canEdit && (
      <div className="row"><button className="btn ghost" onClick={() => ui.open('projectForm', { project: p })}>Edit</button><button className="btn" onClick={() => ui.open('taskForm', { projectId: id })}>Add task</button></div>
    )}>
      <div className="grid g2">
        <div className="card">
          <div className="row"><Badge t={p.status} k="s" /><span className="sm mute">{fmtD(p.start_date)} to {fmtD(p.end_date)} · created by {p.creator_name}</span></div>
          <p>{p.description || 'No description'}</p>
          <div className="bar"><i style={{ width: `${p.progress}%` }} /></div>
          <p className="sm mute">{p.progress}% complete · {st.total_tasks} tasks · <span className={st.overdue ? 'late' : ''}>{st.overdue} overdue</span></p>
          <div className="row sm">{STATUSES.map((s) => <span key={s}><Badge t={s} k="s" /> {st.by_status[s]}</span>)}</div>
        </div>
        <div className="card">
          <h2>Members</h2>
          <div style={{ marginTop: '.5rem' }}>
            {p.members.map((m) => (
              <div className="row act" key={m.id}><span>{m.full_name}</span><span className="sp" />
                {canEdit && <button className="btn ghost xs" onClick={() => remove(m)}>Remove</button>}
              </div>
            ))}
          </div>
          {canEdit && (
            <div className="row" style={{ marginTop: '.7rem' }}>
              <select style={{ flex: 1 }} value={sel} onChange={(e) => setSel(e.target.value)}>
                {candidates.length ? candidates.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>) : <option value="">No unassigned active users</option>}
              </select>
              <button className="btn xs" disabled={!candidates.length} onClick={add}>Assign user</button>
            </div>
          )}
        </div>
      </div>
      <div className="card" style={{ marginTop: '1rem' }}><h2>Tasks</h2><TaskTable items={tasks.items} showProject={false} /></div>
      <div className="card" style={{ marginTop: '1rem' }}><h2>Project activity</h2>{acts.items.length ? acts.items.map((a) => <Activity key={a.id} a={a} />) : <p className="mute">No activity yet.</p>}</div>
    </Page>
  );
}

/* ---------- tasks ---------- */
function TaskTable({ items, showProject = true }) {
  const { ui } = useApp();
  if (!items.length) return <p className="mute">No tasks match.</p>;
  return (
    <div className="tablewrap">
      <table>
        <thead><tr><th>Task</th>{showProject && <th>Project</th>}<th>Assignee</th><th>Priority</th><th>Status</th><th>Deadline</th></tr></thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.id} className="click" onClick={() => ui.open('task', { id: t.id })}>
              <td><b>{t.title}</b>{t.comment_count > 0 && <span className="sm mute"> {t.comment_count} comment{t.comment_count > 1 ? 's' : ''}</span>}</td>
              {showProject && <td>{t.project_name}</td>}
              <td>{t.assignee_name || 'Unassigned'}</td><td><Badge t={t.priority} k="p" /></td><td><Badge t={t.status} k="s" /></td>
              <td className={t.is_overdue ? 'late' : ''}>{fmtD(t.deadline)}{t.is_overdue ? ' (overdue)' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Tasks({ mine }) {
  const { isAdmin, ui } = useApp();
  const [f, setF] = useState({ q: '', status: '', priority: '', project_id: '', sort_by: mine ? 'deadline' : 'created_at', order: mine ? 'asc' : 'desc', page: 1 });
  const { data: projects } = useData(() => (mine ? Promise.resolve([]) : listProjects()), [mine]);
  const { data: d } = useData(() => api((mine ? '/tasks/my?' : '/tasks?') + qs({ ...f, page_size: 10 })), [f, mine]);
  const upd = (k) => (e) => setF({ ...f, [k]: e.target.value, page: 1 });
  return (
    <Page title={mine ? 'My tasks' : isAdmin ? 'All tasks' : 'Assigned tasks'} actions={isAdmin && !mine && <button className="btn" onClick={() => ui.open('taskForm')}>New task</button>}>
      <div className="filters">
        <SearchBox value={f.q} placeholder="Search tasks" onChange={(q) => setF({ ...f, q, page: 1 })} />
        <select value={f.status} onChange={upd('status')}><Options items={STATUSES} blank="Any status" /></select>
        <select value={f.priority} onChange={upd('priority')}><Options items={PRIORITIES} blank="Any priority" /></select>
        {!mine && <select value={f.project_id} onChange={upd('project_id')}><Options items={(projects || []).map((p) => [p.id, p.name])} blank="All projects" /></select>}
        <select value={f.sort_by} onChange={upd('sort_by')}><Options items={[['created_at', 'Sort: created date'], ['deadline', 'Sort: deadline'], ['priority', 'Sort: priority'], ['title', 'Sort: title']]} /></select>
        <select value={f.order} onChange={upd('order')}><Options items={[['asc', 'Ascending'], ['desc', 'Descending']]} /></select>
      </div>
      {d && <div className="card"><TaskTable items={d.items} showProject={!mine} /><Pager m={d} onPage={(page) => setF({ ...f, page })} /></div>}
    </Page>
  );
}

function TaskForm({ task, projectId }) {
  const { ui, run, toast, refresh } = useApp();
  const { data: directory, error: directoryError } = useData(
    () => Promise.all([listProjects(), listUsers()]),
    [],
  );
  const [projects, users] = directory || [[], []];
  const [f, setF] = useState({
    title: task?.title || '', description: task?.description || '', project_id: task?.project_id || projectId || '',
    assignee_id: task?.assignee_id || '', priority: task?.priority || 'Medium', status: task?.status || 'To Do', deadline: task?.deadline || '',
  });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const mine = projects || [];
  const selectedProject = projects.find((p) => String(p.id) === String(f.project_id));
  const memberIds = new Set((selectedProject?.members || []).map((member) => member.id));
  const members = users.filter((u) => u.is_active && memberIds.has(u.id));
  const save = () => run(async () => {
    const body = { title: f.title.trim(), description: f.description, assignee_id: f.assignee_id ? +f.assignee_id : null, priority: f.priority, status: f.status, deadline: f.deadline || null };
    if (task) await api(`/tasks/${task.id}`, { method: 'PUT', body });
    else await api('/tasks', { method: 'POST', body: { ...body, project_id: +f.project_id } });
    ui.close(); toast('Task saved'); refresh();
  });
  return (
    <Modal>
      <h2>{task ? 'Edit task' : 'New task'}</h2>
      <label>Title<input value={f.title} onChange={set('title')} /></label>
      <label>Description<textarea rows="3" value={f.description} onChange={set('description')} /></label>
      <div className="two">
        <label>Project
          <select value={f.project_id} disabled={!!task} onChange={(e) => setF({ ...f, project_id: e.target.value, assignee_id: '' })}>
            <Options items={mine.map((p) => [p.id, p.name])} blank="Select project" />
          </select>
        </label>
        <label>Assignee (assigned project user)
          <select value={f.assignee_id} disabled={!selectedProject || !!directoryError} onChange={set('assignee_id')}>
            <Options items={members.map((m) => [m.id, m.full_name])} blank="Unassigned" />
          </select>
          {directoryError
            ? <span className="sm late">{directoryError}</span>
            : selectedProject
              ? <span className="sm mute">
               only users assigned to this project can be selected. {!members.length && 'Assign users to this project first.'}
              </span>
              : null}
        </label>
        <label>Priority<select value={f.priority} onChange={set('priority')}><Options items={PRIORITIES} /></select></label>
        <label>Status<select value={f.status} onChange={set('status')}><Options items={STATUSES} /></select></label>
      </div>
      <label>Deadline<input type="date" value={f.deadline} onChange={set('deadline')} /></label>
      <div className="row"><div className="sp" /><button className="btn ghost" onClick={ui.close}>Cancel</button><button className="btn" onClick={save}>Save task</button></div>
    </Modal>
  );
}

function TaskDetail({ id }) {
  const { user, isAdmin, ui, run, toast, refresh, go } = useApp();
  const { data, error } = useData(() => Promise.all([api(`/tasks/${id}`), api(`/tasks/${id}/comments`), api(`/tasks/${id}/activity`)]), [id]);
  const [text, setText] = useState('');
  if (error) return <Modal><p>{error}</p><button className="btn" onClick={ui.close}>Close</button></Modal>;
  if (!data) return null;
  const [t, comments, acts] = data;
  const canStatus = isAdmin || t.assignee_id === user.id;
  const setStatus = (status) => run(async () => { await api(`/tasks/${id}/status`, { method: 'PATCH', body: { status } }); toast('Status updated'); refresh(); });
  const post = () => run(async () => { if (!text.trim()) return; await api(`/tasks/${id}/comments`, { method: 'POST', body: { content: text } }); setText(''); refresh(); });
  const del = () => ui.open('confirm', {
    msg: 'Delete this task permanently?',
    onYes: () => run(async () => { await api(`/tasks/${id}`, { method: 'DELETE' }); toast('Task deleted'); refresh(); }),
  });
  return (
    <Modal>
      <div className="row"><h2>{t.title}</h2><span className="sp" /><Badge t={t.priority} k="p" /></div>
      <p>{t.description || 'No description'}</p>
      <div className="two sm">
        <div><span className="mute">Project</span><br /><button className="linkbtn" onClick={() => go('project', t.project_id)}>{t.project_name}</button></div>
        <div><span className="mute">Assignee</span><br />{t.assignee_name || 'Unassigned'}</div>
        <div><span className="mute">Deadline</span><br /><span className={t.is_overdue ? 'late' : ''}>{fmtD(t.deadline)}</span></div>
        <div><span className="mute">Created by</span><br />{t.creator_name}{t.updater_name ? ` · last updated by ${t.updater_name}` : ''}</div>
      </div>
      <label>Status<select value={t.status} disabled={!canStatus} onChange={(e) => setStatus(e.target.value)}><Options items={STATUSES} /></select></label>
      <h3>Comments</h3>
      <div>
        {comments.length ? comments.map((c) => <div className="act" key={c.id}><b>{c.user_name}</b> <span className="sm mute">{ago(c.created_at)}</span><div>{c.content}</div></div>) : <p className="mute sm">No comments yet.</p>}
      </div>
      <div className="row"><input style={{ flex: 1 }} placeholder="Write a comment" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && post()} /><button className="btn" onClick={post}>Post comment</button></div>
      <details><summary className="sm mute" style={{ cursor: 'pointer' }}>Task history ({acts.length})</summary>{acts.map((a) => <Activity key={a.id} a={a} />)}</details>
      <div className="row"><div className="sp" />
        {isAdmin && <><button className="btn bad" onClick={del}>Delete</button><button className="btn ghost" onClick={() => ui.open('taskForm', { task: t })}>Edit task</button></>}
        <button className="btn" onClick={ui.close}>Close</button>
      </div>
    </Modal>
  );
}

/* ---------- update status ---------- */
function Board() {
  const { ui, run, refresh } = useApp();
  const [pid, setPid] = useState('');
  const [over, setOver] = useState(null);
  const { data: projects } = useData(() => listProjects(), []);
  const { data: d } = useData(() => api('/tasks?' + qs({ project_id: pid, page_size: 100, sort_by: 'deadline', order: 'asc' })), [pid]);
  const drop = (e, status) => {
    e.preventDefault(); setOver(null);
    const id = e.dataTransfer.getData('text/plain');
    if (id) run(async () => { try { await api(`/tasks/${id}/status`, { method: 'PATCH', body: { status } }); } finally { refresh(); } });
  };
  return (
    <Page title="Update status" actions={<select value={pid} onChange={(e) => setPid(e.target.value)}><Options items={(projects || []).map((p) => [p.id, p.name])} blank="All projects" /></select>}>
      <div className="board">
        {STATUSES.map((s) => {
          const items = (d?.items || []).filter((t) => t.status === s);
          return (
            <div key={s} className={`col ${over === s ? 'over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(s); }} onDragLeave={() => setOver(null)} onDrop={(e) => drop(e, s)}>
              <div className="row"><h3>{s}</h3><span className="sp" /><span className="sm mute">{items.length}</span></div>
              {items.map((t) => (
                <div key={t.id} className={`kcard p-${t.priority}`} draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', String(t.id))} onClick={() => ui.open('task', { id: t.id })}>
                  <div className="t">{t.title}</div>
                  <div className="sm mute">{t.project_name} · {t.assignee_name || 'Unassigned'}</div>
                  <div className={`sm ${t.is_overdue ? 'late' : 'mute'}`}>{t.priority} · {fmtD(t.deadline)}</div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </Page>
  );
}

/* ---------- users (admin) ---------- */
function Users() {
  const { user, ui, run, refresh } = useApp();
  const [f, setF] = useState({ q: '', page: 1 });
  const { data: d } = useData(() => api('/users?' + qs({ ...f, page_size: 10 })), [f]);
  const toggle = (u) => run(async () => { await api(`/users/${u.id}/active?is_active=${!u.is_active}`, { method: 'PATCH' }); refresh(); });
  return (
    <Page title="Team & users" actions={<button className="btn" onClick={() => ui.open('userForm')}>New user</button>}>
      <div className="filters"><SearchBox value={f.q} placeholder="Search name or email" onChange={(q) => setF({ q, page: 1 })} /></div>
      {d && (
        <div className="card">
          <div className="tablewrap">
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
              <tbody>
                {d.items.map((u) => (
                  <tr key={u.id}>
                    <td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td>
                    <td><span className={`badge ${u.is_active ? 's-Completed' : 's-To-Do'}`}>{u.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td><div className="row">
                      <button className="btn ghost xs" onClick={() => ui.open('userForm', { u })}>Edit</button>
                      {u.id !== user.id && <button className="btn ghost xs" onClick={() => toggle(u)}>{u.is_active ? 'Deactivate' : 'Activate'}</button>}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager m={d} onPage={(page) => setF({ ...f, page })} />
        </div>
      )}
    </Page>
  );
}

function UserForm({ u }) {
  const { ui, run, toast, refresh } = useApp();
  const [f, setF] = useState({ full_name: u?.full_name || '', email: u?.email || '', phone: u?.phone || '', role: u?.role || 'Team Member', is_active: u ? u.is_active : true, password: '' });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = () => run(async () => {
    const body = { full_name: f.full_name.trim(), phone: f.phone || null, role: f.role, is_active: f.is_active };
    if (f.password) body.password = f.password;
    if (u) await api(`/users/${u.id}`, { method: 'PUT', body });
    else await api('/users', { method: 'POST', body: { ...body, email: f.email.trim(), password: f.password } });
    ui.close(); toast('User saved'); refresh();
  });
  return (
    <Modal>
      <h2>{u ? 'Edit user' : 'New user'}</h2>
      <label>Full name<input value={f.full_name} onChange={set('full_name')} /></label>
      <label>Email<input type="email" value={f.email} disabled={!!u} onChange={set('email')} /></label>
      <label>Phone<input value={f.phone} onChange={set('phone')} /></label>
      <div className="two">
        <label>Role<select value={f.role} onChange={set('role')}><Options items={ROLES} /></select></label>
        <label>{u ? 'New password (optional)' : 'Password'}<input type="password" autoComplete="new-password" value={f.password} onChange={set('password')} /></label>
      </div>
      <label className="chk"><input type="checkbox" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} />Account is active</label>
      <div className="row"><div className="sp" /><button className="btn ghost" onClick={ui.close}>Cancel</button><button className="btn" onClick={save}>Save user</button></div>
    </Modal>
  );
}

function Confirm({ msg, onYes }) {
  const { ui } = useApp();
  return (
    <Modal>
      <h2>Are you sure?</h2><p>{msg}</p>
      <div className="row"><div className="sp" /><button className="btn ghost" onClick={ui.close}>Cancel</button><button className="btn bad" onClick={() => { ui.close(); onYes(); }}>Delete</button></div>
    </Modal>
  );
}

/* ---------- shell ---------- */
const NAV = [['dashboard', 'Dashboard'], ['projects', 'Projects'], ['tasks', 'All tasks'], ['my', 'My tasks'], ['board', 'Update status'], ['users', 'Team & users']];

export default function App() {
  const [user, setUser] = useState(session.user());
  const [route, setRoute] = useState({ name: 'dashboard' });
  const [ver, setVer] = useState(0);
  const [modal, setModal] = useState(null);
  const [msg, setMsg] = useState(null);
  const [menu, setMenu] = useState(false);

  const toast = useCallback((text, err) => { setMsg({ text, err }); setTimeout(() => setMsg(null), 3200); }, []);
  const logout = useCallback(() => { session.clear(); setUser(null); setModal(null); }, []);
  useEffect(() => { window.addEventListener('pm-logout', logout); return () => window.removeEventListener('pm-logout', logout); }, [logout]);

  const toastEl = msg && <div className={`toast ${msg.err ? 'err' : ''}`}>{msg.text}</div>;
  if (!user) return <><Auth onLogin={setUser} toast={toast} />{toastEl}</>;

  const ui = { open: (type, props = {}) => setModal({ type, props }), close: () => setModal(null) };
  const ctx = {
    user, ver, ui, toast, isAdmin: user.role === 'Admin',
    refresh: () => setVer((v) => v + 1),
    run: async (fn) => { try { return await fn(); } catch (e) { toast(e.message, true); } },
    go: (name, arg) => { setRoute({ name, arg }); setMenu(false); setModal(null); },
  };

  const views = {
    dashboard: <Dashboard />, projects: <Projects />, project: <ProjectDetail id={route.arg} />,
    tasks: <Tasks key="all" />, my: <Tasks key="mine" mine />, board: <Board />, users: user.role === 'Admin' ? <Users /> : <div className="card">Admins only.</div>,
  };
  const modals = {
    task: TaskDetail, taskForm: TaskForm, projectForm: ProjectForm, userForm: UserForm, confirm: Confirm,
  };
  const ModalView = modal && modals[modal.type];
  const active = route.name === 'project' ? 'projects' : route.name;

  return (
    <Ctx.Provider value={ctx}>
      <div id="app">
        <aside className={menu ? 'open' : ''}>
          <div className="brand">Taskyard</div>
          {NAV.filter(([k]) => k !== 'users' || user.role === 'Admin').map(([k, label]) => (
            <button key={k} className={`nav ${active === k ? 'on' : ''}`} onClick={() => ctx.go(k)}>
              {k === 'tasks' && user.role !== 'Admin' ? 'Assigned tasks' : label}
            </button>
          ))}
          <div className="sp" />
          <div className="sm" style={{ padding: '.5rem .7rem' }}>{user.full_name}<br /><span className="mute">{user.role}</span></div>
          <button className="nav" onClick={logout}>Sign out</button>
        </aside>
        <main>
          <button className="btn ghost" id="burger" onClick={() => setMenu(!menu)} aria-label="Menu" style={{ marginBottom: '.8rem' }}>Menu</button>
          {views[route.name]}
        </main>
      </div>
      {ModalView && <ModalView {...modal.props} />}
      {toastEl}
    </Ctx.Provider>
  );
}
