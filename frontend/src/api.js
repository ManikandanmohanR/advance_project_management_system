// Backend address: set VITE_API_URL in frontend/.env (e.g. VITE_API_URL=http://localhost:8000)
const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v1';

export const session = {
  token: () => localStorage.getItem('pm_token'),
  user: () => JSON.parse(localStorage.getItem('pm_user') || 'null'),
  save(token, user) { localStorage.setItem('pm_token', token); localStorage.setItem('pm_user', JSON.stringify(user)); },
  clear() { localStorage.removeItem('pm_token'); localStorage.removeItem('pm_user'); },
};

export const qs = (o) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, v); });
  return p.toString();
};

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  let payload;
  const token = session.token();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (form) payload = new URLSearchParams(form);
  else if (body) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }

  const res = await fetch(BASE + path, { method, headers, body: payload });
  if (res.status === 401 && token) {
    window.dispatchEvent(new Event('pm-logout'));
    throw new Error('Session expired, please sign in again');
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed');
  return data;
}

export const listUsers = async () => (await api('/users?page_size=100')).items;
export const listProjects = async () => (await api('/projects?page_size=100')).items;
