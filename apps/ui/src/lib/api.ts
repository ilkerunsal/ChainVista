// src/lib/api.ts
// Vite build-time env: docker compose ile build arg olarak geliyor
const API_BASE = (import.meta.env.VITE_API_URL as string) ?? 'http://localhost:5000';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiOptions {
  method?: HttpMethod;
  body?: unknown;
  headers?: Record<string, string>;
  // Opsiyonel: JWT / tenant / role header’ları
  token?: string;            // Authorization: Bearer <token>
  tenantId?: string;         // X-Tenant-Id
  role?: string;             // X-Role (dev/test kolaylığı için)
  // fetch ayarları
  signal?: AbortSignal;
}

function buildHeaders(opts?: ApiOptions): Headers {
  const h = new Headers({
    'Content-Type': 'application/json',
    ...(opts?.headers ?? {}),
  });

  if (opts?.token) h.set('Authorization', `Bearer ${opts.token}`);
  if (opts?.tenantId) h.set('X-Tenant-Id', opts.tenantId);
  if (opts?.role) h.set('X-Role', opts.role);

  return h;
}

async function request<T = unknown>(path: string, opts?: ApiOptions): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: opts?.method ?? 'GET',
    headers: buildHeaders(opts),
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
    signal: opts?.signal,
    // credentials / mode gerekirse buraya:
    // credentials: 'include',
    // mode: 'cors',
  });

  // HTTP 403, 400 vb. durumları da anlamlı hata ile fırlat
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText} @ ${path} — ${text}`);
  }

  // Boş body durumunda (204) boş döndür
  const contentType = res.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    // JSON değilse text döndürmek istersen yorumdan çıkar:
    // const txt = await res.text();
    // @ts-expect-error: JSON değilse çağıran kendisi handle etmeli
    return undefined;
  }

  return res.json() as Promise<T>;
}

// Dışarı basit yardımcılar:
export const apiGet = <T = unknown>(path: string, opts?: ApiOptions) =>
  request<T>(path, { ...opts, method: 'GET' });

export const apiPost = <T = unknown>(path: string, body?: unknown, opts?: ApiOptions) =>
  request<T>(path, { ...opts, method: 'POST', body });

export const apiPut = <T = unknown>(path: string, body?: unknown, opts?: ApiOptions) =>
  request<T>(path, { ...opts, method: 'PUT', body });

export const apiDelete = <T = unknown>(path: string, opts?: ApiOptions) =>
  request<T>(path, { ...opts, method: 'DELETE' });

export { API_BASE };
