/* eslint-disable @typescript-eslint/no-explicit-any */
const BASE = '/api/webapp';

function getInitData(): string {
  const tg = (window as any).Telegram?.WebApp;
  return tg?.initData || '';
}

async function request(path: string, init: RequestInit = {}): Promise<any> {
  const initData = getInitData();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as any || {}),
  };
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
    // also support the tma form if backend prefers
    // headers['Authorization'] = `tma ${initData}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...init,
    headers,
  });
  if (!res.ok) {
    let errBody: any = {};
    try { errBody = await res.json(); } catch {}
    const msg = errBody?.error || `HTTP ${res.status}`;
    const e: any = new Error(msg);
    e.status = res.status;
    throw e;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (p: string) => request(p),
  post: (p: string, body?: any) => request(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: (p: string, body?: any) => request(p, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  del: (p: string) => request(p, { method: 'DELETE' }),
};

export async function fetchPortfolio(params: Record<string, any> = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)); });
  const q = qs.toString();
  return request(`/portfolio${q ? '?' + q : ''}`);
}

export async function toggleNotify(domainId: number | string, enabled: boolean) {
  return api.post(`/domain/${domainId}/toggle`, { enabled });
}

export async function addDomain(domain: string) {
  return api.post('/add', { domain });
}

export async function removeDomain(domainId: number | string) {
  return api.del(`/domain/${domainId}`);
}

export async function bulkAction(action: string, ids: Array<number | string>, extra?: any) {
  return api.post('/bulk', { action, ids, ...extra });
}

export async function updateSettings(patch: Record<string, any>) {
  return api.post('/settings', patch);
}

export async function addWishlist(domain: string) {
  return api.post('/wishlist', { domain });
}

export async function removeWishlist(domain: string) {
  return api.del(`/wishlist/${encodeURIComponent(domain)}`);
}

export async function importDomains(payload: any) {
  return api.post('/import', payload);
}

export async function markAlertsRead(ids: Array<number | string>) {
  return api.post('/alerts/read', { ids });
}

// Types (loose to match design + backend shaping)
export type WebAppDomain = {
  id: number;
  name: string;
  unicode?: string;
  noData?: boolean;
  isWishlist?: boolean;
  daysLeft?: number | null;
  health?: number;
  subCount?: number;
  groups?: any[];
  notify?: Record<string, boolean>;
  flags?: string[];
  cost?: number;
  registrar?: string;
  [k: string]: any;
};

export type PortfolioResponse = {
  items: WebAppDomain[];
  total?: number;
  [k: string]: any;
};

export type WebAppAlert = any;

// Additional fetchers used by screens (map to backend read endpoints from 0066)
export async function fetchDashboard() { return request('/dashboard'); }
export async function fetchCalendar(month?: string) { return request(`/calendar${month ? '?month=' + encodeURIComponent(month) : ''}`); }
export async function fetchAlerts() { return request('/alerts'); }
export async function fetchSettings() { return request('/settings'); }
export async function fetchDomain(id: number | string) { return request(`/domain/${id}`); }
